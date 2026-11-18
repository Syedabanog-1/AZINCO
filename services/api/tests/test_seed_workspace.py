"""[MOCK] dev workspace seeding: guarded to local/ci, RLS-compliant, audited, visible in /me."""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine

from azinco_api.auth.mailer import CAPTURED
from azinco_api.core.config import Environment, Settings
from azinco_api.db.session import create_session_factory
from azinco_api.devtools.seed_workspace import SeedError, mock_name, seed_workspace
from azinco_api.main import create_app
from tests.conftest import TEST_FERNET_KEY, make_settings
from tests.db_helpers import DB_INTEGRATION


def test_mock_name_is_always_tagged() -> None:
    assert mock_name("  Demo   Traders ") == "[MOCK] Demo Traders"
    assert mock_name("[MOCK] Already") == "[MOCK] Already"
    with pytest.raises(SeedError):
        mock_name("   ")


def test_refuses_outside_local_and_ci() -> None:
    settings = make_settings().model_copy(update={"env": Environment("staging")})
    with pytest.raises(SeedError, match="local/ci only"):
        asyncio.run(seed_workspace(None, settings, email="x@example.com", name="X"))  # type: ignore[arg-type]


def _seed(settings: Settings, **kw: str) -> uuid.UUID:
    async def run() -> uuid.UUID:
        engine = create_async_engine(settings.database_url())
        try:
            return await seed_workspace(create_session_factory(engine), settings, **kw)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@pytest.fixture
def settings() -> Settings:
    return Settings().model_copy(
        update={"mail_mode": "capture", "mfa_encryption_key": SecretStr(TEST_FERNET_KEY)}
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings, readiness_checks=[])) as c:
        yield c


@pytest.mark.integration
@DB_INTEGRATION
def test_seeded_workspace_appears_for_the_user(client: TestClient, settings: Settings) -> None:
    email = f"seed-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Tea-in-Karachi-2026!"
    client.post("/api/v1/auth/register", json={"email": email, "password": pw, "display_name": "S"})

    with pytest.raises(SeedError, match="Verify the e-mail"):
        _seed(settings, email=email, name="Too Early")
    with pytest.raises(SeedError, match="No account"):
        _seed(settings, email=f"nobody-{uuid.uuid4().hex[:6]}@example.com", name="X")

    mail = next(m for m in reversed(CAPTURED) if m.to == email)
    token = re.search(r"token=([A-Za-z0-9_\-]+)", mail.body)
    assert token
    client.post("/api/v1/auth/verify-email", json={"token": token.group(1)})
    tenant_id = _seed(settings, email=email, name="Demo Traders", jurisdiction="PK")

    client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    me = client.get("/api/v1/me").json()
    assert [(m["tenant_id"], m["tenant_name"], m["role"]) for m in me["memberships"]] == [
        (str(tenant_id), "[MOCK] Demo Traders", "client_owner")
    ]
    tenant = client.get(f"/api/v1/tenants/{tenant_id}")
    assert tenant.status_code == 200
