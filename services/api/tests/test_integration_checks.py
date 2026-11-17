"""Integration tests against the real Docker stack.

Enabled only when AZINCO_INTEGRATION=1 (the `api-test` compose service sets it).
"""

from __future__ import annotations

import os

import pytest

from azinco_api.core.config import Settings
from azinco_api.health.checks import (
    PostgresCheck,
    PrivilegedRoleError,
    ReadinessCheck,
    RedisCheck,
    StorageCheck,
    run_checks,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("AZINCO_INTEGRATION") != "1", reason="set AZINCO_INTEGRATION=1"
    ),
]


@pytest.fixture
def real_settings() -> Settings:
    return Settings()  # from the container environment


async def test_all_real_checks_pass(real_settings: Settings) -> None:
    checks: list[ReadinessCheck] = [
        PostgresCheck(real_settings),
        RedisCheck(real_settings),
        StorageCheck(real_settings),
    ]
    results = await run_checks(checks, timeout=5)
    assert all(r.ok for r in results), results


async def test_postgres_check_refuses_privileged_role(real_settings: Settings) -> None:
    """If the API were configured with the superuser, readiness must fail (RLS would not hold)."""
    superuser = os.environ.get("POSTGRES_SUPERUSER")
    password = os.environ.get("POSTGRES_SUPERUSER_PASSWORD")
    if not superuser or not password:
        pytest.skip("superuser credentials not provided to the test container")
    check = PostgresCheck(real_settings, user=superuser, password=password)
    with pytest.raises(PrivilegedRoleError):
        await check()


async def test_wrong_storage_bucket_fails(real_settings: Settings) -> None:
    bad = real_settings.model_copy(update={"s3_bucket_documents": "does-not-exist-bucket"})
    results = await run_checks([StorageCheck(bad)], timeout=5)
    assert not results[0].ok
