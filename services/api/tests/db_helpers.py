"""Helpers for integration tests that talk to the real PostgreSQL as the app role."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from azinco_api.core.config import Settings

DB_INTEGRATION = pytest.mark.skipif(
    os.environ.get("AZINCO_INTEGRATION_DB") != "1", reason="set AZINCO_INTEGRATION_DB=1"
)


async def connect(user: str | None = None, password: str | None = None) -> asyncpg.Connection:
    s = Settings()
    return await asyncpg.connect(
        host=s.postgres_host,
        port=s.postgres_port,
        database=s.postgres_db,
        user=user or s.db_app_user,
        password=password or s.db_app_password.get_secret_value(),
    )


async def set_context(
    conn: asyncpg.Connection, tenant_id: uuid.UUID | None, user_id: uuid.UUID | None = None
) -> None:
    await conn.execute(
        "SELECT set_config('app.tenant_id', $1, true), set_config('app.user_id', $2, true)",
        str(tenant_id) if tenant_id else "",
        str(user_id) if user_id else "",
    )


async def create_tenant(
    conn: asyncpg.Connection, name: str = "Synthetic Traders", jurisdiction: str = "PK"
) -> uuid.UUID:
    """Create a tenant the RLS way: context first, then insert. Leaves context on it."""
    tid = uuid.uuid4()
    await set_context(conn, tid)
    await conn.execute(
        "INSERT INTO app.tenants (id, name, home_jurisdiction) VALUES ($1, $2, $3)",
        tid,
        name,
        jurisdiction,
    )
    return tid


async def create_user(conn: asyncpg.Connection, email: str, tenant_id: uuid.UUID) -> uuid.UUID:
    """Create a user as themselves (registration path) and make them owner of the tenant."""
    uid = uuid.uuid4()
    await set_context(conn, tenant_id, uid)
    await conn.execute(
        "INSERT INTO app.users (id, email, display_name, user_type) VALUES ($1, $2, $3, 'client')",
        uid,
        email,
        email.split("@")[0],
    )
    await conn.execute(
        "INSERT INTO app.tenant_memberships (tenant_id, user_id, role) "
        "VALUES ($1, $2, 'client_owner')",
        tenant_id,
        uid,
    )
    return uid


async def rollback_connection() -> AsyncIterator[asyncpg.Connection]:
    conn = await connect()
    tx = conn.transaction()
    await tx.start()
    try:
        yield conn
    finally:
        await tx.rollback()
        await conn.close()
