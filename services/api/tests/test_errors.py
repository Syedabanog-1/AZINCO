"""RFC 9457 problem+json responses."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from tests.conftest import AppFactory


@pytest.fixture
def app_with_test_routes(app_factory: AppFactory) -> Iterator[TestClient]:
    app: FastAPI = app_factory()

    @app.get("/_test/boom")
    async def boom() -> None:
        raise RuntimeError("internal detail: password=hunter2")

    @app.get("/_test/needs-int")
    async def needs_int(n: int = Query(...)) -> dict[str, int]:
        return {"n": n}

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_404_is_problem_json(client: TestClient) -> None:
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["instance"] == "/does-not-exist"
    assert body["request_id"] == resp.headers["X-Request-ID"]


def test_validation_error_does_not_echo_input(app_with_test_routes: TestClient) -> None:
    resp = app_with_test_routes.get("/_test/needs-int", params={"n": "secret-value-123"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["title"] == "Unprocessable Content"
    assert body["errors"][0]["loc"] == ["query", "n"]
    assert "secret-value-123" not in resp.text


def test_unhandled_exception_hides_details(app_with_test_routes: TestClient) -> None:
    resp = app_with_test_routes.get("/_test/boom")
    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert "hunter2" not in resp.text
    assert "internal detail" not in resp.text
    assert resp.json()["request_id"] == resp.headers["X-Request-ID"]
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_method_not_allowed_is_problem_json(client: TestClient) -> None:
    resp = client.post("/health")
    assert resp.status_code == 405
    assert resp.json()["title"] == "Method Not Allowed"
