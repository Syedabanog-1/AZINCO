"""Settings validation, docs exposure and log masking."""

from __future__ import annotations

import json
from typing import Any

import pytest
import structlog
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from azinco_api.core.config import Environment, Settings
from azinco_api.core.logging import MASK, configure_logging, mask_sensitive
from tests.conftest import AppFactory, make_settings


def test_required_secrets_missing_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("AZINCO_DB_APP_PASSWORD", "REDIS_URL", "S3_ENDPOINT", "S3_ACCESS_KEY"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZINCO_ENV", "dev")
    monkeypatch.setenv("AZINCO_DB_APP_PASSWORD", "x" * 20)
    monkeypatch.setenv("REDIS_URL", "redis://:r@redis:6379/0")
    monkeypatch.setenv("S3_ENDPOINT", "http://storage:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "a" * 20)
    monkeypatch.setenv("S3_SECRET_KEY", "s" * 20)
    monkeypatch.setenv("AZINCO_LOG_LEVEL", "debug")
    s = Settings()
    assert s.env is Environment.DEV
    assert s.log_level == "DEBUG"
    assert s.base_currency == "PKR"
    assert "x" * 20 not in repr(s)


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(log_level="LOUD")


def test_invalid_base_currency_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(base_currency="rupees")


@pytest.mark.parametrize("env", [Environment.DEV, Environment.STAGING, Environment.PROD])
def test_placeholder_secret_rejected_outside_local(env: Environment) -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        make_settings(env=env, s3_secret_key=SecretStr("change-me-secret-key"))


def test_placeholder_allowed_in_local() -> None:
    assert make_settings(env=Environment.LOCAL, s3_secret_key=SecretStr("change-me")).env


def test_docs_disabled_in_prod(app_factory: AppFactory) -> None:
    prod = make_settings(env=Environment.PROD)
    with TestClient(app_factory(app_settings=prod)) as c:
        assert c.get("/openapi.json").status_code == 404
        assert c.get("/docs").status_code == 404


def test_docs_enabled_outside_prod(client: TestClient) -> None:
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    assert {"/health", "/ready"} <= set(spec.json()["paths"])


def test_mask_sensitive_nested() -> None:
    event: dict[str, Any] = {
        "event": "x",
        "password": "p",
        "Authorization": "Bearer t",
        "nested": {"api_key": "k", "ok": 1, "items": [{"db_password": "z"}]},
    }
    out = mask_sensitive(None, "info", event)
    assert out["password"] == MASK
    assert out["Authorization"] == MASK
    assert out["nested"]["api_key"] == MASK
    assert out["nested"]["ok"] == 1
    assert out["nested"]["items"][0]["db_password"] == MASK


def test_log_output_is_json_and_masked(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger("t").info("login", user="u1", password="hunter2")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(line)
    assert record["event"] == "login"
    assert record["password"] == MASK
    assert "hunter2" not in line
