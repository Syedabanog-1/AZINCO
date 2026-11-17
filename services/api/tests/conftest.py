"""Shared fixtures. Unit tests never touch real services."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from azinco_api.core.config import Environment, Settings
from azinco_api.health.checks import ReadinessCheck
from azinco_api.main import create_app


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": Environment.CI,
        "log_level": "WARNING",
        "db_app_password": SecretStr("test-app-password"),
        "redis_url": SecretStr("redis://:test-redis@localhost:6379/0"),
        "s3_endpoint": "http://localhost:9000",
        "s3_access_key": SecretStr("test-access"),
        "s3_secret_key": SecretStr("test-secret-key"),
        "readiness_timeout_seconds": 0.5,
    }
    values.update(overrides)
    return Settings.model_validate(values)


class FakeCheck:
    """[MOCK] readiness check used only in unit tests."""

    def __init__(self, name: str, error: Exception | None = None, delay: float = 0.0) -> None:
        self.name = name
        self._error = error
        self._delay = delay

    async def __call__(self) -> None:
        if self._delay:
            import asyncio

            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error


AppFactory = Callable[..., FastAPI]


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app_factory(settings: Settings) -> AppFactory:
    def _factory(
        checks: Sequence[ReadinessCheck] | None = None, app_settings: Settings | None = None
    ) -> FastAPI:
        default: list[ReadinessCheck] = [FakeCheck("postgres"), FakeCheck("redis")]
        return create_app(app_settings or settings, checks if checks is not None else default)

    return _factory


@pytest.fixture
def client(app_factory: AppFactory) -> Iterator[TestClient]:
    with TestClient(app_factory(), raise_server_exceptions=False) as c:
        yield c
