"""Write audit events inside the caller's transaction (fail-closed).

Because the event is appended in the same database transaction as the business change, either
both are committed or neither is: an action can never happen without its audit record.
"""

from __future__ import annotations

import enum
import json
import uuid
from collections.abc import Mapping
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from azinco_api.core.logging import mask_value

_APPEND = text(
    "SELECT audit.append_event(:tenant, CAST(:actor_type AS audit.actor_type), :actor, :action, "
    ":resource_type, :resource_id, :request_id, CAST(:details AS jsonb))"
)


class ActorType(enum.StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


async def record(
    session: AsyncSession,
    action: str,
    *,
    actor_type: ActorType = ActorType.HUMAN,
    actor_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | uuid.UUID | None = None,
    details: Mapping[str, Any] | None = None,
) -> int:
    """Append one audit event; returns its id. Sensitive keys in `details` are masked."""
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    payload = json.dumps(mask_value(dict(details or {})), sort_keys=True, default=str)
    event_id = await session.scalar(
        _APPEND,
        {
            "tenant": tenant_id,
            "actor_type": actor_type.value,
            "actor": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id is not None else None,
            "request_id": str(request_id) if request_id else None,
            "details": payload,
        },
    )
    if event_id is None:  # pragma: no cover - append_event always returns an id or raises
        raise RuntimeError("audit append returned no id")
    return int(event_id)
