"""Schema `app` against a real PostgreSQL (Step 0.5).

Enabled with AZINCO_INTEGRATION_DB=1 (the `api-test` container sets it). Every test runs in a
transaction that is rolled back, so the runtime role never needs DELETE rights.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from tests.db_helpers import (
    DB_INTEGRATION,
    connect,
    create_tenant,
    create_user,
    rollback_connection,
    set_context,
)

pytestmark = [pytest.mark.integration, DB_INTEGRATION]


@pytest.fixture
async def app_conn() -> AsyncIterator[asyncpg.Connection]:
    async for conn in rollback_connection():
        yield conn


async def _new_tenant(conn: asyncpg.Connection, name: str = "Synthetic Traders") -> uuid.UUID:
    return await create_tenant(conn, name)


async def test_tenant_defaults(app_conn: asyncpg.Connection) -> None:
    tid = await _new_tenant(app_conn)
    row = await app_conn.fetchrow(
        "SELECT status, base_currency, funds_handling FROM app.tenants WHERE id = $1", tid
    )
    assert row is not None
    assert dict(row) == {
        "status": "onboarding",
        "base_currency": "PKR",
        "funds_handling": "ledger",  # Option A by default (BS §5.3)
    }


async def test_user_and_membership(app_conn: asyncpg.Connection) -> None:
    tid = await _new_tenant(app_conn)
    uid = await create_user(app_conn, "Owner@Example.test", tid)
    status = await app_conn.fetchval("SELECT status FROM app.users WHERE id = $1", uid)
    assert status == "pending_verification"


async def test_email_is_case_insensitive_unique(app_conn: asyncpg.Connection) -> None:
    tid = await _new_tenant(app_conn)
    await create_user(app_conn, "a@x.test", tid)
    with pytest.raises(asyncpg.UniqueViolationError):
        await create_user(app_conn, "A@X.TEST", tid)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO app.tenants (id, name, home_jurisdiction) VALUES ($1, 'X', 'pk')",
        "INSERT INTO app.tenants (id, name, home_jurisdiction) VALUES ($1, '   ', 'PK')",
        "INSERT INTO app.tenants (id, name, home_jurisdiction, base_currency) "
        "VALUES ($1, 'X', 'PK', 'rs')",
        "INSERT INTO app.users (id, email, display_name, user_type) "
        "VALUES ($1, 'no-at-sign', 'X', 'client')",
    ],
)
async def test_check_constraints(app_conn: asyncpg.Connection, sql: str) -> None:
    # Row id == context, so RLS allows the row and the CHECK constraint is what rejects it.
    row_id = uuid.uuid4()
    await set_context(app_conn, row_id, row_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await app_conn.execute(sql, row_id)


async def test_invalid_enum_value_rejected(app_conn: asyncpg.Connection) -> None:
    row_id = uuid.uuid4()
    await set_context(app_conn, row_id)
    with pytest.raises(asyncpg.InvalidTextRepresentationError):
        await app_conn.execute(
            "INSERT INTO app.tenants (id, name, home_jurisdiction, funds_handling) "
            "VALUES ($1, 'X', 'PK', 'escrow')",
            row_id,
        )


async def test_updated_at_maintained_by_database(app_conn: asyncpg.Connection) -> None:
    tid = await _new_tenant(app_conn)
    # now() is fixed within a transaction, so force a visible difference first.
    await app_conn.execute("UPDATE app.tenants SET updated_at = '2000-01-01' WHERE id = $1", tid)
    await app_conn.execute("UPDATE app.tenants SET name = 'Renamed' WHERE id = $1", tid)
    year = await app_conn.fetchval(
        "SELECT extract(year FROM updated_at)::int FROM app.tenants WHERE id = $1", tid
    )
    assert year > 2000


async def test_app_role_cannot_delete(app_conn: asyncpg.Connection) -> None:
    tid = await _new_tenant(app_conn)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app_conn.execute("DELETE FROM app.tenants WHERE id = $1", tid)


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TABLE app.sneaky (i int)",
        "ALTER TABLE app.tenants ADD COLUMN sneaky int",
        "DROP TABLE app.tenants",
        "TRUNCATE app.tenants",
    ],
)
async def test_app_role_cannot_change_schema(app_conn: asyncpg.Connection, ddl: str) -> None:
    with pytest.raises(
        (asyncpg.InsufficientPrivilegeError, asyncpg.exceptions.DependentObjectsStillExistError)
    ):
        await app_conn.execute(ddl)


async def test_readonly_role_cannot_write() -> None:
    password = os.environ.get("AZINCO_DB_READONLY_PASSWORD")
    if not password:
        pytest.skip("AZINCO_DB_READONLY_PASSWORD not provided")
    conn = await connect("azinco_readonly", password)
    try:
        assert await conn.fetchval("SELECT count(*) >= 0 FROM app.tenants")
        with pytest.raises(
            (asyncpg.InsufficientPrivilegeError, asyncpg.ReadOnlySQLTransactionError)
        ):
            await conn.execute(
                "INSERT INTO app.tenants (name, home_jurisdiction) VALUES ('X', 'PK')"
            )
    finally:
        await conn.close()
