"""Tenant isolation suite (Step 0.6, NFR-SEC-01, BS §14 "data leak between clients").

Runs against the real PostgreSQL as the runtime role `azinco_app`. These tests are the
CI gate that proves one client can never read or change another client's data.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from azinco_api.core.config import Settings
from azinco_api.db.session import create_session_factory
from azinco_api.db.tenancy import tenant_session
from tests.db_helpers import (
    DB_INTEGRATION,
    connect,
    create_tenant,
    create_user,
    rollback_connection,
    set_context,
)

pytestmark = [pytest.mark.integration, DB_INTEGRATION]

APP_TABLES = ("tenants", "users", "tenant_memberships", "platform_roles")


@pytest.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    async for c in rollback_connection():
        yield c


@pytest.fixture
async def two_tenants(conn: asyncpg.Connection) -> dict[str, uuid.UUID]:
    a = await create_tenant(conn, "Tenant A Traders")
    ua = await create_user(conn, "owner-a@example.test", a)
    b = await create_tenant(conn, "Tenant B Mills")
    ub = await create_user(conn, "owner-b@example.test", b)
    return {"a": a, "ua": ua, "b": b, "ub": ub}


# ------------------------------------------------------------------ catalog guards
async def test_every_app_table_has_forced_rls_and_a_policy(conn: asyncpg.Connection) -> None:
    """Fails as soon as someone adds a table to schema app without RLS."""
    rows = await conn.fetch(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
               (SELECT count(*) FROM pg_policies p
                 WHERE p.schemaname = 'app' AND p.tablename = c.relname) AS policies
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'app' AND c.relkind IN ('r', 'p')
        """
    )
    assert {r["relname"] for r in rows} >= set(APP_TABLES)
    bad = [r["relname"] for r in rows if not (r["relrowsecurity"] and r["relforcerowsecurity"])]
    assert bad == [], f"tables without ENABLE+FORCE RLS: {bad}"
    no_policy = [r["relname"] for r in rows if r["policies"] == 0]
    assert no_policy == [], f"tables without any policy: {no_policy}"


async def test_no_runtime_role_bypasses_rls(conn: asyncpg.Connection) -> None:
    bypass = await conn.fetch(
        "SELECT rolname FROM pg_roles WHERE rolname LIKE 'azinco\\_%' "
        "AND (rolbypassrls OR rolsuper)"
    )
    assert bypass == []


# ------------------------------------------------------------------ no context
@pytest.mark.parametrize("table", APP_TABLES)
async def test_no_context_sees_nothing(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID], table: str
) -> None:
    await set_context(conn, None, None)
    assert await conn.fetchval(f"SELECT count(*) FROM app.{table}") == 0  # noqa: S608


async def test_no_context_cannot_insert_tenant(conn: asyncpg.Connection) -> None:
    await set_context(conn, None)
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="row-level security"):
        await conn.execute("INSERT INTO app.tenants (name, home_jurisdiction) VALUES ('X', 'PK')")


async def test_malformed_context_is_an_error_not_a_match(conn: asyncpg.Connection) -> None:
    await conn.execute("SELECT set_config('app.tenant_id', 'not-a-uuid', true)")
    with pytest.raises(asyncpg.InvalidTextRepresentationError):
        await conn.fetchval("SELECT count(*) FROM app.tenants")


# ------------------------------------------------------------------ cross-tenant reads
async def test_tenant_sees_only_itself(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID]
) -> None:
    await set_context(conn, two_tenants["a"])
    names = [r["name"] for r in await conn.fetch("SELECT name FROM app.tenants")]
    assert names == ["Tenant A Traders"]
    memberships = await conn.fetch("SELECT tenant_id FROM app.tenant_memberships")
    assert {r["tenant_id"] for r in memberships} == {two_tenants["a"]}


async def test_users_of_other_tenant_are_invisible(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID]
) -> None:
    await set_context(conn, two_tenants["a"], two_tenants["ua"])
    emails = {r["email"] for r in await conn.fetch("SELECT email FROM app.users")}
    assert emails == {"owner-a@example.test"}
    assert (
        await conn.fetchval("SELECT count(*) FROM app.users WHERE id = $1", two_tenants["ub"]) == 0
    )


async def test_expired_membership_hides_user(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID]
) -> None:
    await set_context(conn, two_tenants["a"])
    await conn.execute(
        "UPDATE app.tenant_memberships SET expires_at = now() - interval '1 day' "
        "WHERE user_id = $1",
        two_tenants["ua"],
    )
    assert await conn.fetchval("SELECT count(*) FROM app.users") == 0


# ------------------------------------------------------------------ cross-tenant writes
async def test_cannot_update_other_tenant(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID]
) -> None:
    await set_context(conn, two_tenants["a"])
    result = await conn.execute(
        "UPDATE app.tenants SET name = 'hijacked' WHERE id = $1", two_tenants["b"]
    )
    assert result == "UPDATE 0"
    await set_context(conn, two_tenants["b"])
    assert await conn.fetchval("SELECT name FROM app.tenants") == "Tenant B Mills"


async def test_cannot_move_row_to_other_tenant(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID]
) -> None:
    await set_context(conn, two_tenants["a"])
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="row-level security"):
        await conn.execute(
            "UPDATE app.tenant_memberships SET tenant_id = $1 WHERE tenant_id = $2",
            two_tenants["b"],
            two_tenants["a"],
        )


async def test_cannot_insert_membership_into_other_tenant(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID]
) -> None:
    await set_context(conn, two_tenants["a"])
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="row-level security"):
        await conn.execute(
            "INSERT INTO app.tenant_memberships (tenant_id, user_id, role) "
            "VALUES ($1, $2, 'client_staff')",
            two_tenants["b"],
            two_tenants["ua"],
        )


async def test_cannot_update_another_users_profile(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID]
) -> None:
    other = await create_user(conn, "staff-a@example.test", two_tenants["a"])
    await set_context(conn, two_tenants["a"], two_tenants["ua"])
    result = await conn.execute(
        "UPDATE app.users SET display_name = 'changed' WHERE id = $1", other
    )
    assert result == "UPDATE 0"


async def test_cannot_register_user_with_foreign_id(conn: asyncpg.Connection) -> None:
    await set_context(conn, None, uuid.uuid4())
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="row-level security"):
        await conn.execute(
            "INSERT INTO app.users (id, email, display_name, user_type) "
            "VALUES ($1, 'x@example.test', 'X', 'client')",
            uuid.uuid4(),
        )


async def test_platform_roles_not_self_grantable(
    conn: asyncpg.Connection, two_tenants: dict[str, uuid.UUID]
) -> None:
    await set_context(conn, two_tenants["a"], two_tenants["ua"])
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="row-level security"):
        await conn.execute(
            "INSERT INTO app.platform_roles (user_id, role) VALUES ($1, 'platform_admin')",
            two_tenants["ua"],
        )


# ------------------------------------------------------------------ pooled connections
async def test_context_never_leaks_across_transactions() -> None:
    """With a single pooled connection, the next transaction must start without context."""
    settings = Settings()
    engine = create_async_engine(settings.database_url(), pool_size=1, max_overflow=0)
    factory = create_session_factory(engine)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            current = await session.scalar(text("SELECT app.current_tenant_id()"))
            assert current == tenant_id
        async with factory() as session:
            leaked = await session.scalar(text("SELECT app.current_tenant_id()"))
            assert leaked is None
    finally:
        await engine.dispose()


async def test_tenant_session_rejects_string_ids() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url())
    factory = create_session_factory(engine)
    try:
        with pytest.raises(TypeError):
            async with tenant_session(factory, "not-a-uuid"):  # type: ignore[arg-type]
                pass
    finally:
        await engine.dispose()


async def test_tenant_session_rolls_back_on_error() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url())
    factory = create_session_factory(engine)
    tenant_id = uuid.uuid4()
    try:
        with pytest.raises(RuntimeError):
            async with tenant_session(factory, tenant_id) as session:
                await session.execute(
                    text(
                        "INSERT INTO app.tenants (id, name, home_jurisdiction) "
                        "VALUES (:id, 'Rollback Co', 'PK')"
                    ),
                    {"id": tenant_id},
                )
                raise RuntimeError("boom")
        async with tenant_session(factory, tenant_id) as session:
            assert await session.scalar(text("SELECT count(*) FROM app.tenants")) == 0
    finally:
        await engine.dispose()


async def test_readonly_role_also_isolated() -> None:
    import os

    password = os.environ.get("AZINCO_DB_READONLY_PASSWORD")
    if not password:
        pytest.skip("AZINCO_DB_READONLY_PASSWORD not provided")
    ro = await connect("azinco_readonly", password)
    try:
        assert await ro.fetchval("SELECT count(*) FROM app.tenants") == 0
    finally:
        await ro.close()
