"""Ledger operations. Every call runs in ONE transaction as role `azinco_ledger` with the caller's
tenant and actor set transaction-locally (ADR-0003), so RLS and the database invariants apply.

Posting, reversal posting and period reopening go through the SECURITY DEFINER functions of
migration 0005, which demand a reviewer approval; this layer never bypasses them.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import asyncpg

from azinco_ledger.domain import DraftIn, LedgerRuleError, prepare_lines


@dataclass(frozen=True, slots=True)
class Caller:
    tenant_id: uuid.UUID
    actor_id: uuid.UUID  # the human or agent user on whose behalf the call is made


class NotFoundError(LookupError):
    pass


@asynccontextmanager
async def tenant_tx(pool: asyncpg.Pool, caller: Caller) -> AsyncIterator[asyncpg.Connection]:
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "SELECT set_config('app.tenant_id', $1, true), set_config('app.user_id', $2, true)",
            str(caller.tenant_id),
            str(caller.actor_id),
        )
        yield cast(asyncpg.Connection, conn)  # pool proxy behaves like a connection


async def _audit(
    conn: asyncpg.Connection,
    caller: Caller,
    action: str,
    resource_type: str,
    resource: uuid.UUID,
    details: dict[str, Any],
) -> None:
    await conn.execute(
        "SELECT audit.append_event($1, 'system'::audit.actor_type, $2, $3, $4, $5, NULL, "
        "$6::jsonb)",
        caller.tenant_id,
        caller.actor_id,
        action,
        resource_type,
        str(resource),
        json.dumps(details, sort_keys=True, default=str),
    )


# ------------------------------------------------------------------ reads
_JOURNAL_SQL = """
SELECT id, entity_id, journal_date, description, status::text AS status, source::text AS source,
       reverses_id, journal_no, ledger_seq, approval_id, period_id, posted_at, created_at,
       encode(row_hash, 'hex') AS row_hash
  FROM ledger.journals WHERE id = $1
"""
_LINES_SQL = """
SELECT line_no, account_id, debit, credit, currency, fx_rate, base_debit, base_credit,
       evidence_type::text AS evidence_type, document_id, extraction_field_id, rule_version_id,
       tax_code, memo
  FROM ledger.journal_lines WHERE journal_id = $1 ORDER BY line_no
"""


async def _journal(conn: asyncpg.Connection, journal_id: uuid.UUID) -> dict[str, Any]:
    row = await conn.fetchrow(_JOURNAL_SQL, journal_id)
    if row is None:  # RLS hides other tenants' journals: same answer as "does not exist"
        raise NotFoundError("journal not found")
    lines = [dict(r) for r in await conn.fetch(_LINES_SQL, journal_id)]
    return {**dict(row), "lines": lines}


async def get_journal(pool: asyncpg.Pool, caller: Caller, journal_id: uuid.UUID) -> dict[str, Any]:
    async with tenant_tx(pool, caller) as conn:
        return await _journal(conn, journal_id)


async def verify_chain(pool: asyncpg.Pool, caller: Caller) -> dict[str, Any]:
    async with tenant_tx(pool, caller) as conn:
        row = await conn.fetchrow("SELECT * FROM ledger.verify_chain($1)", caller.tenant_id)
    assert row is not None  # noqa: S101 - the function always returns one row
    return dict(row)


# ------------------------------------------------------------------ chart of accounts & periods
async def create_account(
    pool: asyncpg.Pool,
    caller: Caller,
    *,
    entity_id: uuid.UUID,
    code: str,
    name: str,
    account_class: str,
    is_suspense: bool,
    currency: str | None,
) -> uuid.UUID:
    async with tenant_tx(pool, caller) as conn:
        account_id: uuid.UUID = await conn.fetchval(
            "INSERT INTO ledger.accounts (tenant_id, entity_id, code, name, class, is_suspense, "
            "currency) VALUES ($1, $2, $3, $4, $5::ledger.account_class, $6, $7) RETURNING id",
            caller.tenant_id,
            entity_id,
            code,
            name,
            account_class,
            is_suspense,
            currency,
        )
        await _audit(
            conn,
            caller,
            "ledger.account.created",
            "account",
            account_id,
            {"code": code, "class": account_class},
        )
        return account_id


async def create_period(
    pool: asyncpg.Pool, caller: Caller, *, entity_id: uuid.UUID, start: date, end: date
) -> uuid.UUID:
    async with tenant_tx(pool, caller) as conn:
        period_id: uuid.UUID = await conn.fetchval(
            "INSERT INTO ledger.periods (tenant_id, entity_id, start_date, end_date) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            caller.tenant_id,
            entity_id,
            start,
            end,
        )
        await _audit(
            conn, caller, "ledger.period.created", "period", period_id, {"start": start, "end": end}
        )
        return period_id


async def lock_period(pool: asyncpg.Pool, caller: Caller, period_id: uuid.UUID) -> None:
    async with tenant_tx(pool, caller) as conn:
        await conn.execute("SELECT ledger.lock_period($1)", period_id)


async def reopen_period(
    pool: asyncpg.Pool, caller: Caller, period_id: uuid.UUID, approval_id: uuid.UUID
) -> None:
    async with tenant_tx(pool, caller) as conn:
        await conn.execute("SELECT ledger.reopen_period($1, $2)", period_id, approval_id)


# ------------------------------------------------------------------ journals
async def create_draft(pool: asyncpg.Pool, caller: Caller, draft: DraftIn) -> dict[str, Any]:
    async with tenant_tx(pool, caller) as conn:
        functional = await conn.fetchval(
            "SELECT functional_currency FROM app.entities WHERE id = $1", draft.entity_id
        )
        if functional is None:
            raise NotFoundError("entity not found")
        prepared = prepare_lines(draft, functional)  # L1/L7 in code, before any write
        journal_id: uuid.UUID = await conn.fetchval(
            "INSERT INTO ledger.journals (tenant_id, entity_id, journal_date, description, source, "
            "created_by) VALUES ($1, $2, $3, $4, $5::ledger.journal_source, $6) RETURNING id",
            caller.tenant_id,
            draft.entity_id,
            draft.journal_date,
            draft.description,
            draft.source,
            caller.actor_id,
        )
        await conn.executemany(
            "INSERT INTO ledger.journal_lines (tenant_id, entity_id, journal_id, line_no, "
            "account_id, debit, credit, currency, fx_rate, base_debit, base_credit, "
            "evidence_type, document_id, extraction_field_id, rule_version_id, tax_code, memo) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::ledger.evidence_type,$13,$14,$15,"
            "$16,$17)",
            [
                (
                    caller.tenant_id,
                    draft.entity_id,
                    journal_id,
                    p.line_no,
                    p.line.account_id,
                    p.line.debit,
                    p.line.credit,
                    p.line.currency,
                    p.line.fx_rate,
                    p.base_debit,
                    p.base_credit,
                    p.line.evidence_type.value,
                    p.line.document_id,
                    p.line.extraction_field_id,
                    p.line.rule_version_id,
                    p.line.tax_code,
                    p.line.memo,
                )
                for p in prepared
            ],
        )
        total = sum((p.base_debit for p in prepared), Decimal(0))
        await _audit(
            conn,
            caller,
            "ledger.journal.drafted",
            "journal",
            journal_id,
            {"lines": len(prepared), "base_total": total, "source": draft.source},
        )
        return await _journal(conn, journal_id)


async def post_journal(
    pool: asyncpg.Pool, caller: Caller, journal_id: uuid.UUID, approval_id: uuid.UUID
) -> dict[str, Any]:
    async with tenant_tx(pool, caller) as conn:
        await conn.execute("SELECT ledger.post_journal($1, $2)", journal_id, approval_id)
        return await _journal(conn, journal_id)


async def create_reversal(
    pool: asyncpg.Pool,
    caller: Caller,
    journal_id: uuid.UUID,
    reversal_date: date,
    description: str,
) -> dict[str, Any]:
    async with tenant_tx(pool, caller) as conn:
        reversal_id: uuid.UUID = await conn.fetchval(
            "SELECT ledger.create_reversal($1, $2, $3, $4)",
            journal_id,
            reversal_date,
            description,
            caller.actor_id,
        )
        return await _journal(conn, reversal_id)


async def discard_journal(
    pool: asyncpg.Pool, caller: Caller, journal_id: uuid.UUID, reason: str
) -> dict[str, Any]:
    async with tenant_tx(pool, caller) as conn:
        await conn.execute("SELECT ledger.discard_journal($1, $2)", journal_id, reason)
        return await _journal(conn, journal_id)


def json_ready(value: Any) -> Any:
    """Decimals as strings (exact), datetimes ISO, UUIDs as text - for API responses."""
    if isinstance(value, dict):
        return {k: json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


__all__ = [
    "Caller",
    "LedgerRuleError",
    "NotFoundError",
    "create_account",
    "create_draft",
    "create_period",
    "create_reversal",
    "discard_journal",
    "get_journal",
    "json_ready",
    "lock_period",
    "post_journal",
    "reopen_period",
    "verify_chain",
]
