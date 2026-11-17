"""Tenant context for database work (Step 0.6, ADR-0003).

Every piece of tenant data is read or written inside `tenant_session(...)`. It opens a
transaction and sets the context with `set_config(..., true)` (transaction-local), so:

* PostgreSQL Row-Level Security filters every query to the tenant in context;
* the context disappears at COMMIT/ROLLBACK and can never leak to the next request that
  reuses the pooled connection.

Who may act for which tenant (membership + role) is decided before this call by the
auth/RBAC layer (Step 0.7). RLS is the last line of defence, not the only one.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_SET_CONTEXT = text(
    "SELECT set_config('app.tenant_id', :tenant_id, true), "
    "set_config('app.user_id', :user_id, true)"
)


def _as_uuid_text(value: uuid.UUID | None, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, uuid.UUID):  # guards against passing raw strings from requests
        raise TypeError(f"{name} must be uuid.UUID, got {type(value).__name__}")
    return str(value)


@asynccontextmanager
async def tenant_session(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None = None,
) -> AsyncIterator[AsyncSession]:
    """Yield a session inside one transaction with the tenant/user context applied.

    The transaction commits when the block exits normally and rolls back on any exception.
    """
    params = {
        "tenant_id": _as_uuid_text(tenant_id, "tenant_id"),
        "user_id": _as_uuid_text(user_id, "user_id"),
    }
    async with factory() as session, session.begin():
        await session.execute(_SET_CONTEXT, params)
        yield session
