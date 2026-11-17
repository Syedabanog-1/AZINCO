"""Tenant-scoped audit trail endpoints (FR-ADM-02, BS §10.2 audit explorer)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from azinco_api.auth.deps import get_session_factory, require_tenant_permission
from azinco_api.auth.rbac import Permission
from azinco_api.auth.service import Principal
from azinco_api.db.tenancy import tenant_session

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/audit-events", tags=["audit"])

Factory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
AuditReader = Annotated[Principal, Depends(require_tenant_permission(Permission.AUDIT_READ))]


_LIST_SQL = text(
    "SELECT seq, occurred_at, actor_type::text AS actor_type, actor_id, action, "
    "resource_type, resource_id, request_id, details, "
    "encode(prev_hash, 'hex') AS prev_hash, encode(row_hash, 'hex') AS row_hash "
    "FROM audit.audit_events "
    "WHERE tenant_id = :t AND (CAST(:before AS bigint) IS NULL OR seq < :before) "
    "ORDER BY seq DESC LIMIT :lim"
)


class AuditEventOut(BaseModel):
    seq: int
    occurred_at: datetime
    actor_type: str
    actor_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    request_id: str | None
    details: dict[str, Any]
    prev_hash: str
    row_hash: str


class AuditPage(BaseModel):
    events: list[AuditEventOut]
    next_before_seq: int | None


class ChainVerification(BaseModel):
    events: int
    ok: bool
    first_bad_seq: int | None


@router.get("", response_model=AuditPage)
async def list_events(
    tenant_id: uuid.UUID,
    factory: Factory,
    principal: AuditReader,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
) -> AuditPage:
    async with tenant_session(factory, tenant_id, principal.user_id) as s:
        rows = (
            (
                await s.execute(
                    _LIST_SQL,
                    {"t": tenant_id, "before": before_seq, "lim": limit},
                )
            )
            .mappings()
            .all()
        )
    events = [AuditEventOut(**dict(r)) for r in rows]
    next_cursor = events[-1].seq if len(events) == limit and events[-1].seq > 1 else None
    return AuditPage(events=events, next_before_seq=next_cursor)


@router.get("/verify", response_model=ChainVerification)
async def verify(
    tenant_id: uuid.UUID, factory: Factory, principal: AuditReader
) -> ChainVerification:
    async with tenant_session(factory, tenant_id, principal.user_id) as s:
        row = (
            (await s.execute(text("SELECT * FROM audit.verify_chain(:t)"), {"t": tenant_id}))
            .mappings()
            .one()
        )
    return ChainVerification(
        events=int(row["events"]), ok=bool(row["ok"]), first_bad_seq=row["first_bad_seq"]
    )
