"""End-to-end auth flows through the API against the real PostgreSQL (Step 0.7).

E-mail uses the in-memory [MOCK] outbox (AZINCO_MAIL_MODE=capture). Every test uses fresh
synthetic e-mail addresses because runtime roles cannot delete rows.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator

import pyotp
import pytest
from fastapi.testclient import TestClient

from azinco_api.auth.mailer import CAPTURED
from azinco_api.core.config import Settings
from azinco_api.main import create_app
from tests.conftest import TEST_FERNET_KEY
from tests.db_helpers import DB_INTEGRATION, connect, create_tenant, set_context

pytestmark = [pytest.mark.integration, DB_INTEGRATION]

PASSWORD = "Tea-in-Karachi-2026!"


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings().model_copy(
        update={
            "mail_mode": "capture",
            "mfa_encryption_key": __import__("pydantic").SecretStr(TEST_FERNET_KEY),
        }
    )
    with TestClient(create_app(settings, readiness_checks=[])) as c:
        yield c


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


def _token_for(email: str) -> str:
    mail = next(m for m in reversed(CAPTURED) if m.to == email)
    match = re.search(r"token=([A-Za-z0-9_\-]+)", mail.body)
    assert match
    return match.group(1)


def _register_and_verify(c: TestClient, email: str) -> None:
    assert (
        c.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD, "display_name": "Synthetic"},
        ).status_code
        == 202
    )
    assert c.post("/api/v1/auth/verify-email", json={"token": _token_for(email)}).status_code == 200


def _login(c: TestClient, email: str, code: str | None = None) -> dict[str, object]:
    resp = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD, "code": code})
    assert resp.status_code == 200, resp.text
    body: dict[str, object] = resp.json()
    return body


def _csrf(c: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": c.cookies.get("azinco_csrf") or ""}


async def _grant_membership(email: str, role: str) -> uuid.UUID:
    conn = await connect()
    try:
        async with conn.transaction():
            await set_context(conn, None)
            row = await conn.fetchrow("SELECT id FROM app.auth_find_user($1)", email)
            assert row is not None
            user_id = row["id"]
            tenant_id = await create_tenant(conn, f"Synthetic {role} Co")
            await set_context(conn, tenant_id, user_id)
            await conn.execute(
                "INSERT INTO app.tenant_memberships (tenant_id, user_id, role) VALUES ($1, $2, $3)",
                tenant_id,
                user_id,
                role,
            )
        return tenant_id
    finally:
        await conn.close()


# ------------------------------------------------------------------ happy path
def test_register_verify_login_me_logout(client: TestClient) -> None:
    email = _email()
    _register_and_verify(client, email)
    me = _login(client, email)
    assert me["email"] == email and me["mfa_required"] is False and me["mfa_satisfied"] is True
    session_cookie = next(c for c in client.cookies.jar if c.name == "azinco_session")
    assert session_cookie.has_nonstandard_attr("HttpOnly")
    assert client.get("/api/v1/me").json()["email"] == email
    assert client.post("/api/v1/auth/logout", headers=_csrf(client)).status_code == 204
    assert client.get("/api/v1/me").status_code == 401


def test_session_token_is_not_stored_in_clear(client: TestClient) -> None:
    import asyncio

    email = _email()
    _register_and_verify(client, email)
    _login(client, email)
    token = client.cookies.get("azinco_session") or ""

    async def _count() -> int:
        conn = await connect()
        try:
            await set_context(conn, None)
            return int(
                await conn.fetchval(
                    "SELECT count(*) FROM app.sessions WHERE token_hash = convert_to($1, 'UTF8')",
                    token,
                )
            )
        finally:
            await conn.close()

    assert asyncio.run(_count()) == 0


# ------------------------------------------------------------------ registration safety
def test_duplicate_registration_looks_identical(client: TestClient) -> None:
    email = _email()
    body = {"email": email, "password": PASSWORD, "display_name": "A"}
    first = client.post("/api/v1/auth/register", json=body)
    mails_before = len([m for m in CAPTURED if m.to == email])
    second = client.post("/api/v1/auth/register", json=body | {"email": email.upper()})
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert len([m for m in CAPTURED if m.to.lower() == email]) == mails_before


def test_weak_password_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register", json={"email": _email(), "password": "short", "display_name": "A"}
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "weak_password"


def test_invalid_verification_token(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/verify-email", json={"token": "x" * 43})
    assert resp.status_code == 400 and resp.json()["code"] == "invalid_token"


# ------------------------------------------------------------------ login safety
def test_unverified_account_cannot_sign_in(client: TestClient) -> None:
    email = _email()
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": "A"}
    )
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 403


def test_wrong_password_and_unknown_user_give_same_answer(client: TestClient) -> None:
    email = _email()
    _register_and_verify(client, email)
    wrong = client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong-pass-123!"})
    unknown = client.post(
        "/api/v1/auth/login", json={"email": _email(), "password": "Wrong-pass-123!"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_lockout_after_repeated_failures(client: TestClient) -> None:
    email = _email()
    _register_and_verify(client, email)
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong-pass-123!"})
    locked = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert locked.status_code == 429


def test_logout_requires_csrf_header(client: TestClient) -> None:
    email = _email()
    _register_and_verify(client, email)
    _login(client, email)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 403 and resp.json()["code"] == "csrf_failed"


def test_tampered_session_cookie_is_rejected(client: TestClient) -> None:
    client.cookies.set("azinco_session", "forged-" + "x" * 40)
    assert client.get("/api/v1/me").status_code == 401


# ------------------------------------------------------------------ MFA
def test_mfa_enrolment_and_login_with_code(client: TestClient) -> None:
    email = _email()
    _register_and_verify(client, email)
    _login(client, email)
    setup = client.post("/api/v1/auth/mfa/setup", headers=_csrf(client)).json()
    assert setup["qr_svg"].lstrip().startswith("<svg")
    secret = setup["secret"]
    assert (
        client.post(
            "/api/v1/auth/mfa/confirm",
            headers=_csrf(client),
            json={"code": pyotp.TOTP(secret).now()},
        ).status_code
        == 204
    )
    client.post("/api/v1/auth/logout", headers=_csrf(client))

    no_code = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert no_code.status_code == 401 and no_code.json()["code"] == "mfa_code_required"
    bad = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD, "code": "000001"}
    )
    assert bad.status_code == 401
    me = _login(client, email, pyotp.TOTP(secret).now())
    assert me["mfa_enabled"] is True


# ------------------------------------------------------------------ RBAC + MFA policy + RLS
def test_reviewer_must_set_up_mfa_before_tenant_access(client: TestClient) -> None:
    import asyncio

    email = _email()
    _register_and_verify(client, email)
    tenant_id = asyncio.run(_grant_membership(email, "reviewer"))
    me = _login(client, email)
    assert me["mfa_required"] is True and me["mfa_satisfied"] is False
    blocked = client.get(f"/api/v1/tenants/{tenant_id}")
    assert blocked.status_code == 403 and blocked.json()["code"] == "mfa_setup_required"

    secret = client.post("/api/v1/auth/mfa/setup", headers=_csrf(client)).json()["secret"]
    client.post(
        "/api/v1/auth/mfa/confirm", headers=_csrf(client), json={"code": pyotp.TOTP(secret).now()}
    )
    assert client.get(f"/api/v1/tenants/{tenant_id}").status_code == 200


def test_client_owner_sees_own_tenant_but_not_others(client: TestClient) -> None:
    import asyncio

    email = _email()
    _register_and_verify(client, email)
    own = asyncio.run(_grant_membership(email, "client_owner"))
    other_email = _email()
    _register_and_verify(client, other_email)
    other = asyncio.run(_grant_membership(other_email, "client_owner"))

    _login(client, email)
    mine = client.get(f"/api/v1/tenants/{own}")
    assert mine.status_code == 200 and mine.json()["funds_handling"] == "ledger"
    theirs = client.get(f"/api/v1/tenants/{other}")
    assert theirs.status_code == 404  # not 403: never confirm that another tenant exists
    me = client.get("/api/v1/me").json()
    assert [m["tenant_id"] for m in me["memberships"]] == [str(own)]
    assert "payment:make" in me["memberships"][0]["permissions"]
