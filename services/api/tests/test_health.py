"""Liveness, readiness, request id and security headers."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.conftest import AppFactory, FakeCheck


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "azinco-api"
    assert body["environment"] == "ci"


def test_request_id_generated_and_security_headers_present(client: TestClient) -> None:
    resp = client.get("/health")
    uuid.UUID(resp.headers["X-Request-ID"])  # raises if not a UUID
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Cache-Control"] == "no-store"


def test_valid_incoming_request_id_is_echoed(client: TestClient) -> None:
    rid = str(uuid.uuid4())
    assert client.get("/health", headers={"X-Request-ID": rid}).headers["X-Request-ID"] == rid


def test_invalid_incoming_request_id_is_replaced(client: TestClient) -> None:
    resp = client.get("/health", headers={"X-Request-ID": "<script>alert(1)</script>"})
    assert resp.headers["X-Request-ID"] != "<script>alert(1)</script>"
    uuid.UUID(resp.headers["X-Request-ID"])


def test_ready_all_ok(client: TestClient) -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert {c["name"] for c in body["components"]} == {"postgres", "redis"}
    assert all(c["status"] == "ok" and c["detail"] is None for c in body["components"])


def test_ready_reports_failure_with_503_and_no_secret_leak(app_factory: AppFactory) -> None:
    leaky = RuntimeError("connect failed for postgres://azinco_app:SuperSecret@db/azinco")
    app = app_factory([FakeCheck("postgres", error=leaky), FakeCheck("redis")])
    with TestClient(app) as c:
        resp = c.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    pg = next(x for x in body["components"] if x["name"] == "postgres")
    assert pg == {**pg, "status": "fail", "detail": "RuntimeError"}
    assert "SuperSecret" not in resp.text


def test_ready_times_out_slow_dependency(app_factory: AppFactory) -> None:
    app = app_factory([FakeCheck("storage", delay=2.0)])  # timeout in settings is 0.5 s
    with TestClient(app) as c:
        resp = c.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["components"][0]["detail"] == "TimeoutError"
