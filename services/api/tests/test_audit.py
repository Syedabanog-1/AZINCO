"""Audit log (Step 0.8): hash chain, immutability, tamper detection, concurrency, RLS, wiring.

Runs against the real PostgreSQL. Tests that need the bootstrap superuser (to prove that even
an administrator cannot silently rewrite history) skip when its credentials are not provided.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import re
import uuid
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pyotp
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from azinco_api.auth.mailer import CAPTURED
from azinco_api.core.config import Settings
from azinco_api.main import create_app
from tests.conftest import TEST_FERNET_KEY
from tests.db_helpers import DB_INTEGRATION, connect, create_tenant, set_context

pytestmark = [pytest.mark.integration, DB_INTEGRATION]

APPEND = "SELECT audit.append_event($1, $2::audit.actor_type, $3, $4, $5, $6, $7, $8::jsonb)"


async def _append(
    conn: asyncpg.Connection, tenant: uuid.UUID | None, action: str, details: dict[str, object]
) -> int:
    return int(
        await conn.fetchval(
            APPEND, tenant, "system", None, action, None, None, None, json.dumps(details)
        )
    )


async def _superuser() -> asyncpg.Connection | None:
    user = os.environ.get("POSTGRES_SUPERUSER")
    password = os.environ.get("POSTGRES_SUPERUSER_PASSWORD")
    if not user:
        return None
    return await connect(user, password or "unused")


@pytest.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    c = await connect()
    try:
        yield c
    finally:
        await c.close()


# ------------------------------------------------------------------ chain
async def test_events_form_a_verifiable_chain(conn: asyncpg.Connection) -> None:
    tenant = uuid.uuid4()
    for i in range(5):
        await _append(conn, tenant, "test.chain_event", {"i": i})
    row = await conn.fetchrow("SELECT * FROM audit.verify_chain($1)", tenant)
    assert row is not None and dict(row) == {"events": 5, "ok": True, "first_bad_seq": None}

    async with conn.transaction():  # context is transaction-local by design (ADR-0003)
        await set_context(conn, tenant)
        rows = await conn.fetch(
            "SELECT seq, prev_hash, row_hash FROM audit.audit_events "
            "WHERE tenant_id = $1 ORDER BY seq",
            tenant,
        )
    assert [r["seq"] for r in rows] == [1, 2, 3, 4, 5]
    assert rows[0]["prev_hash"] == b"\x00" * 32
    for prev, cur in itertools.pairwise(rows):
        assert cur["prev_hash"] == prev["row_hash"]


async def test_sensitive_details_are_masked_by_the_writer() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from azinco_api.audit.writer import record
    from azinco_api.db.session import create_session_factory
    from azinco_api.db.tenancy import tenant_session

    tenant = uuid.uuid4()
    engine = create_async_engine(Settings().database_url())
    try:
        factory = create_session_factory(engine)
        async with tenant_session(factory, tenant) as s:
            await record(
                s,
                "test.masking",
                tenant_id=tenant,
                details={"password": "hunter2", "nested": {"api_key": "k"}, "ok": 1},
            )
        async with tenant_session(factory, tenant) as s:
            from sqlalchemy import text

            details = await s.scalar(
                text("SELECT details FROM audit.audit_events WHERE tenant_id = :t"), {"t": tenant}
            )
    finally:
        await engine.dispose()
    assert details == {"password": "***", "nested": {"api_key": "***"}, "ok": 1}


# ------------------------------------------------------------------ immutability
@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO audit.audit_events (stream_id, seq, occurred_at, actor_type, action, "
        "prev_hash, row_hash) VALUES (gen_random_uuid(), 1, now(), 'system', 'forged.event', "
        "'\\x00', '\\x00')",
        "UPDATE audit.audit_events SET action = 'tampered.event'",
        "DELETE FROM audit.audit_events",
        "TRUNCATE audit.audit_events",
    ],
)
async def test_runtime_role_cannot_write_directly(conn: asyncpg.Connection, sql: str) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await conn.execute(sql)


async def test_even_superuser_cannot_update_or_delete(conn: asyncpg.Connection) -> None:
    tenant = uuid.uuid4()
    await _append(conn, tenant, "test.immutable", {})
    su = await _superuser()
    if su is None:
        pytest.skip("POSTGRES_SUPERUSER not provided")
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="append-only"):
            await su.execute(
                "UPDATE audit.audit_events SET action = 'x.y.z' WHERE tenant_id = $1", tenant
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="append-only"):
            await su.execute("DELETE FROM audit.audit_events WHERE tenant_id = $1", tenant)
    finally:
        await su.close()


async def test_tampering_is_detected(conn: asyncpg.Connection) -> None:
    """Simulate an attacker with DB superuser rights who disables the trigger and edits a row."""
    tenant = uuid.uuid4()
    for i in range(4):
        await _append(conn, tenant, "test.tamper_target", {"amount": f"{100 + i}.00"})
    su = await _superuser()
    if su is None:
        pytest.skip("POSTGRES_SUPERUSER not provided")
    try:
        tx = su.transaction()
        await tx.start()
        await su.execute(
            "ALTER TABLE audit.audit_events DISABLE TRIGGER trg_audit_no_update_delete"
        )
        await su.execute(
            'UPDATE audit.audit_events SET details = \'{"amount": "999.00"}\' '
            "WHERE tenant_id = $1 AND seq = 2",
            tenant,
        )
        row = await su.fetchrow("SELECT * FROM audit.verify_chain($1)", tenant)
        await tx.rollback()  # leave the shared database untouched
    finally:
        await su.close()
    assert row is not None and row["ok"] is False and row["first_bad_seq"] == 2


# ------------------------------------------------------------------ concurrency
async def test_concurrent_writers_keep_one_unbroken_chain() -> None:
    tenant = uuid.uuid4()
    conns = [await connect() for _ in range(5)]

    async def worker(c: asyncpg.Connection, w: int) -> None:
        for i in range(5):
            await _append(c, tenant, "test.concurrent", {"worker": w, "i": i})

    try:
        await asyncio.gather(*(worker(c, w) for w, c in enumerate(conns)))
        row = await conns[0].fetchrow("SELECT * FROM audit.verify_chain($1)", tenant)
    finally:
        for c in conns:
            await c.close()
    assert row is not None and row["ok"] is True and row["events"] == 25


# ------------------------------------------------------------------ RLS
async def test_tenants_only_read_their_own_audit_trail(conn: asyncpg.Connection) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    await _append(conn, a, "test.rls_a", {})
    await _append(conn, b, "test.rls_b", {})
    async with conn.transaction():
        await set_context(conn, a)
        actions = {r["action"] for r in await conn.fetch("SELECT action FROM audit.audit_events")}
    assert actions == {"test.rls_a"}
    async with conn.transaction():
        await set_context(conn, None)
        assert await conn.fetchval("SELECT count(*) FROM audit.audit_events") == 0


# ------------------------------------------------------------------ wiring through the API
@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings().model_copy(
        update={"mail_mode": "capture", "mfa_encryption_key": SecretStr(TEST_FERNET_KEY)}
    )
    with TestClient(create_app(settings, readiness_checks=[])) as c:
        yield c


def _register_verify_login(c: TestClient) -> tuple[str, str]:
    email = f"audit-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Tea-in-Karachi-2026!"
    c.post("/api/v1/auth/register", json={"email": email, "password": pw, "display_name": "A"})
    mail = next(m for m in reversed(CAPTURED) if m.to == email)
    token = re.search(r"token=([A-Za-z0-9_\-]+)", mail.body)
    assert token
    c.post("/api/v1/auth/verify-email", json={"token": token.group(1)})
    c.post("/api/v1/auth/login", json={"email": email, "password": "Wrong-pass-123!"})
    assert c.post("/api/v1/auth/login", json={"email": email, "password": pw}).status_code == 200
    return email, c.get("/api/v1/me").json()["id"]


def test_auth_actions_are_audited(client: TestClient) -> None:
    _, user_id = _register_verify_login(client)

    async def _actions() -> list[str]:
        su = await _superuser()
        if su is None:
            pytest.skip("POSTGRES_SUPERUSER not provided")
        try:
            rows = await su.fetch(
                "SELECT action FROM audit.audit_events WHERE actor_id = $1 ORDER BY id",
                uuid.UUID(user_id),
            )
            ok = await su.fetchval("SELECT ok FROM audit.verify_chain(NULL)")
        finally:
            await su.close()
        assert ok is True
        return [r["action"] for r in rows]

    assert asyncio.run(_actions()) == [
        "user.registered",
        "user.email_verified",
        "auth.login.failed",
        "auth.login.succeeded",
    ]


def test_audit_api_requires_permission_and_mfa(client: TestClient) -> None:
    email, user_id = _register_verify_login(client)

    async def _setup() -> uuid.UUID:
        c = await connect()
        try:
            async with c.transaction():
                tenant = await create_tenant(c, "Audited Co")
                await set_context(c, tenant, uuid.UUID(user_id))
                await c.execute(
                    "INSERT INTO app.tenant_memberships (tenant_id, user_id, role) "
                    "VALUES ($1, $2, 'reviewer')",
                    tenant,
                    uuid.UUID(user_id),
                )
            for i in range(3):
                await _append(c, tenant, "test.api_visible", {"i": i})
            return tenant
        finally:
            await c.close()

    tenant = asyncio.run(_setup())
    # Reviewer without MFA: blocked.
    blocked = client.get(f"/api/v1/tenants/{tenant}/audit-events")
    assert blocked.status_code == 403
    csrf = {"X-CSRF-Token": client.cookies.get("azinco_csrf") or ""}
    secret = client.post("/api/v1/auth/mfa/setup", headers=csrf).json()["secret"]
    client.post("/api/v1/auth/mfa/confirm", headers=csrf, json={"code": pyotp.TOTP(secret).now()})

    page = client.get(f"/api/v1/tenants/{tenant}/audit-events?limit=2")
    assert page.status_code == 200
    body = page.json()
    assert [e["seq"] for e in body["events"]] == [3, 2] and body["next_before_seq"] == 2
    assert len(body["events"][0]["row_hash"]) == 64
    assert client.get(f"/api/v1/tenants/{tenant}/audit-events/verify").json() == {
        "events": 3,
        "ok": True,
        "first_bad_seq": None,
    }
    other = uuid.uuid4()
    assert client.get(f"/api/v1/tenants/{other}/audit-events").status_code == 404
    del email
