"""Schema `app` against a real PostgreSQL (Step 0.5).

Enabled with AZINCO_INTEGRATION_DB=1 (the `api-test` container sets it). Every test runs in a
transaction that is rolled back, so the runtime role never needs DELETE rights.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import asyncpg
import pytest

from azinco_api.core.config import Settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("AZINCO_INTEGRATION_DB") != "1", reason="set AZINCO_INTEGRATION_DB=1"
    ),
]


async def _connect(user: str, password: str) -> asyncpg.Connection:
    s = Settings()
    return await asyncpg.connect(
        host=s.postgres_host,
        port=s.postgres_port,
        database=s.postgres_db,
        user=user,
        password=password,
    )


@pytest.fixture
async def app_conn() -> AsyncIterator[asyncpg.Connection]:
    s = Settings()
    conn = await _connect(s.db_app_user, s.db_app_password.get_secret_value())
    tx = conn.transaction()
    await tx.start()
    try:
        yield conn
    finally:
        await tx.rollback()
        await conn.close()


async def _new_tenant(conn: asyncpg.Connection, name: str = "Synthetic Traders") -> object:
    return await conn.fetchval(
        "INSERT INTO app.tenants (name, home_jurisdiction) VALUES ($1, 'PK') RETURNING id", name
    )


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
    uid = await app_conn.fetchval(
        "INSERT INTO app.users (email, display_name, user_type) "
        "VALUES ('Owner@Example.test', 'Owner', 'client') RETURNING id"
    )
    await app_conn.execute(
        "INSERT INTO app.tenant_memberships (tenant_id, user_id, role) "
        "VALUES ($1, $2, 'client_owner')",
        tid,
        uid,
    )
    status = await app_conn.fetchval("SELECT status FROM app.users WHERE id = $1", uid)
    assert status == "pending_verification"


async def test_email_is_case_insensitive_unique(app_conn: asyncpg.Connection) -> None:
    await app_conn.execute(
        "INSERT INTO app.users (email, display_name, user_type) VALUES ('a@x.test', 'A', 'client')"
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await app_conn.execute(
            "INSERT INTO app.users (email, display_name, user_type) "
            "VALUES ('A@X.TEST', 'B', 'client')"
        )


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO app.tenants (name, home_jurisdiction) VALUES ('X', 'pk')",
        "INSERT INTO app.tenants (name, home_jurisdiction) VALUES ('   ', 'PK')",
        "INSERT INTO app.tenants (name, home_jurisdiction, base_currency) VALUES ('X', 'PK', 'rs')",
        "INSERT INTO app.users (email, display_name, user_type) "
        "VALUES ('no-at-sign', 'X', 'client')",
    ],
)
async def test_check_constraints(app_conn: asyncpg.Connection, sql: str) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await app_conn.execute(sql)


async def test_invalid_enum_value_rejected(app_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.InvalidTextRepresentationError):
        await app_conn.execute(
            "INSERT INTO app.tenants (name, home_jurisdiction, funds_handling) "
            "VALUES ('X', 'PK', 'escrow')"
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
    conn = await _connect("azinco_readonly", password)
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
