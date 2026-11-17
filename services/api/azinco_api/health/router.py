"""GET /health (liveness) and GET /ready (readiness of dependencies)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from azinco_api import __version__
from azinco_api.core.config import Settings
from azinco_api.health.checks import ReadinessCheck, run_checks

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


class ComponentStatus(BaseModel):
    name: str
    status: Literal["ok", "fail"]
    latency_ms: float
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    components: list[ComponentStatus]


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_readiness_checks(request: Request) -> Sequence[ReadinessCheck]:
    checks: Sequence[ReadinessCheck] = request.app.state.readiness_checks
    return checks


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: Annotated[Settings, Depends(get_app_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok", service="azinco-api", version=__version__, environment=settings.env.value
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "A dependency is not ready"}},
    summary="Readiness probe (PostgreSQL, Redis, object storage)",
)
async def ready(
    response: Response,
    settings: Annotated[Settings, Depends(get_app_settings)],
    checks: Annotated[Sequence[ReadinessCheck], Depends(get_readiness_checks)],
) -> ReadinessResponse:
    results = await run_checks(checks, settings.readiness_timeout_seconds)
    all_ok = all(r.ok for r in results)
    response.status_code = 200 if all_ok else 503
    return ReadinessResponse(
        status="ready" if all_ok else "not_ready",
        components=[
            ComponentStatus(
                name=r.name,
                status="ok" if r.ok else "fail",
                latency_ms=r.latency_ms,
                detail=r.detail,
            )
            for r in results
        ],
    )
