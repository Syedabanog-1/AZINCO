"""Readiness checks for PostgreSQL, Redis and object storage.

Each check raises on failure. Failure details reported to clients contain only the
exception type name, never the message (messages can contain hosts, users or DSNs).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import asyncpg
import boto3
from botocore.config import Config
from redis.asyncio import Redis

from azinco_api.core.config import Settings


class ReadinessCheck(Protocol):
    name: str

    async def __call__(self) -> None: ...


class PrivilegedRoleError(RuntimeError):
    """The API connected with a superuser or BYPASSRLS role — tenant isolation would not hold."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    latency_ms: float
    detail: str | None = None


class PostgresCheck:
    name = "postgres"

    def __init__(self, settings: Settings, user: str | None = None, password: str | None = None):
        self._settings = settings
        self._user = user or settings.db_app_user
        self._password = password or settings.db_app_password.get_secret_value()

    async def __call__(self) -> None:
        s = self._settings
        conn = await asyncpg.connect(
            host=s.postgres_host,
            port=s.postgres_port,
            user=self._user,
            password=self._password,
            database=s.postgres_db,
            timeout=s.readiness_timeout_seconds,
        )
        try:
            privileged = await conn.fetchval(
                "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
            if privileged is not False:
                raise PrivilegedRoleError
        finally:
            await conn.close()


class RedisCheck:
    name = "redis"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(self) -> None:
        timeout = self._settings.readiness_timeout_seconds
        client = Redis.from_url(
            self._settings.redis_url.get_secret_value(),
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
        try:
            if not await client.ping():
                raise ConnectionError
        finally:
            await client.aclose()


class StorageCheck:
    name = "storage"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _head_bucket(self) -> None:
        s = self._settings
        client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint,
            region_name=s.s3_region,
            aws_access_key_id=s.s3_access_key.get_secret_value(),
            aws_secret_access_key=s.s3_secret_key.get_secret_value(),
            config=Config(
                connect_timeout=s.readiness_timeout_seconds,
                read_timeout=s.readiness_timeout_seconds,
                retries={"max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )
        client.head_bucket(Bucket=s.s3_bucket_documents)

    async def __call__(self) -> None:
        await asyncio.to_thread(self._head_bucket)


def default_checks(settings: Settings) -> list[ReadinessCheck]:
    return [PostgresCheck(settings), RedisCheck(settings), StorageCheck(settings)]


async def _run_one(check: ReadinessCheck, timeout: float) -> CheckResult:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(check(), timeout=timeout)
    except Exception as exc:  # every failure must become a result, never propagate
        return CheckResult(
            check.name, False, round((time.perf_counter() - started) * 1000, 2), type(exc).__name__
        )
    return CheckResult(check.name, True, round((time.perf_counter() - started) * 1000, 2))


async def run_checks(checks: Sequence[ReadinessCheck], timeout: float) -> list[CheckResult]:
    return list(await asyncio.gather(*(_run_one(c, timeout) for c in checks)))
