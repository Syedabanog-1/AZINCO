"""Application factory.

Run with:  uvicorn azinco_api.main:create_app --factory --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from azinco_api import __version__
from azinco_api.auth.router import router as auth_router
from azinco_api.core.config import Settings, get_settings
from azinco_api.core.errors import register_exception_handlers
from azinco_api.core.logging import configure_logging, get_logger
from azinco_api.core.middleware import RequestContextMiddleware
from azinco_api.db.session import create_engine, create_session_factory
from azinco_api.health.checks import ReadinessCheck, default_checks
from azinco_api.health.router import router as health_router


def create_app(
    settings: Settings | None = None,
    readiness_checks: Sequence[ReadinessCheck] | None = None,
    engine: AsyncEngine | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    # Creating the engine does not connect; connections open lazily per request.
    db_engine = engine or create_engine(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await db_engine.dispose()

    app = FastAPI(
        lifespan=lifespan,
        title="AZINCO API",
        version=__version__,
        description=(
            "AZINCO public REST API. AI prepares, deterministic code calculates, "
            "a qualified Reviewer of Record approves."
        ),
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.db_engine = db_engine
    app.state.session_factory = create_session_factory(db_engine)
    app.state.readiness_checks = (
        list(readiness_checks) if readiness_checks is not None else default_checks(settings)
    )

    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router)

    get_logger("azinco.api").info(
        "api.configured", environment=settings.env.value, docs=settings.docs_enabled
    )
    return app
