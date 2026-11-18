"""Internal HTTP API of the Ledger Service (blueprint §3.5 "Internal"). Never published to the host.

Authentication [Recommended, ADR-0016]: `Authorization: Bearer <service token>`.
  * API token    - every operation; posting/reopening still need a reviewer approval id that
                   the database verifies (MFA reviewer, single use).
  * worker token - create drafts and read only. Agents can never post (blueprint AP-2).
Caller context: `X-Tenant-Id` and `X-Actor-Id` (the user on whose behalf the call is made).
Errors are RFC 9457 problem+json with a stable `code`.
"""

# No `from __future__ import annotations`: FastAPI must see the real dependency types of the
# routes defined inside create_app().
import enum
import hmac
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any, Literal

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from azinco_ledger import __version__, service
from azinco_ledger.config import LedgerSettings, get_settings
from azinco_ledger.domain import DraftIn, LedgerRuleError
from azinco_ledger.service import Caller, NotFoundError

PROBLEM = "application/problem+json"


class Scope(enum.StrEnum):
    API = "api"
    WORKER = "worker"


class ProblemError(HTTPException):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(status_code=status, detail=detail)
        self.code = code


def _problem(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        {
            "type": "about:blank",
            "title": code.replace("_", " "),
            "status": status,
            "code": code,
            "detail": detail,
        },
        status_code=status,
        media_type=PROBLEM,
    )


# Database errors -> (status, code). The DB raises these when an invariant is broken.
_PG_ERRORS: tuple[tuple[type[Exception], int, str], ...] = (
    (asyncpg.InsufficientPrivilegeError, 403, "not_authorised"),
    (asyncpg.NoDataFoundError, 404, "not_found"),
    (asyncpg.ExclusionViolationError, 409, "period_overlap"),
    (asyncpg.UniqueViolationError, 409, "conflict"),
    (asyncpg.ForeignKeyViolationError, 422, "unknown_reference"),
    (asyncpg.CheckViolationError, 422, "ledger_rule"),
    (asyncpg.InvalidTextRepresentationError, 422, "invalid_value"),
)


# ------------------------------------------------------------------ request bodies
class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AccountIn(_Body):
    entity_id: uuid.UUID
    code: Annotated[str, Field(pattern=r"^[0-9A-Za-z][0-9A-Za-z.\-]{0,19}$")]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    account_class: Literal[
        "asset", "liability", "equity", "revenue", "cogs", "opex", "other", "tax"
    ]
    is_suspense: bool = False
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None


class PeriodIn(_Body):
    entity_id: uuid.UUID
    start_date: date
    end_date: date


class PostIn(_Body):
    journal_id: uuid.UUID
    approval_id: uuid.UUID


class ReverseIn(_Body):
    journal_id: uuid.UUID
    reversal_date: date
    description: Annotated[str, Field(min_length=1, max_length=500)]


class DiscardIn(_Body):
    journal_id: uuid.UUID
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class ReopenIn(_Body):
    approval_id: uuid.UUID


class Created(_Body):
    id: uuid.UUID


# ------------------------------------------------------------------ app
PoolFactory = Callable[[LedgerSettings], Awaitable[asyncpg.Pool]]


async def default_pool(settings: LedgerSettings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        min_size=settings.pool_min,
        max_size=settings.pool_max,
        command_timeout=30,
    )


def create_app(
    settings: LedgerSettings | None = None, pool_factory: PoolFactory = default_pool
) -> FastAPI:
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.pool = await pool_factory(cfg)
        try:
            yield
        finally:
            await app.state.pool.close()

    app = FastAPI(
        title="AZINCO Ledger Service (internal)",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if cfg.env.value == "production" else "/docs",
        redoc_url=None,
    )

    # ---------------------------------------------------------------- errors
    @app.exception_handler(ProblemError)
    async def _problem_error(_r: Request, exc: ProblemError) -> JSONResponse:
        return _problem(exc.status_code, exc.code, str(exc.detail))

    @app.exception_handler(LedgerRuleError)
    async def _rule_error(_r: Request, exc: LedgerRuleError) -> JSONResponse:
        return _problem(422, exc.code, str(exc))

    @app.exception_handler(NotFoundError)
    async def _not_found(_r: Request, exc: NotFoundError) -> JSONResponse:
        return _problem(404, "not_found", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _invalid(_r: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return _problem(422, "invalid_request", f"{where}: {first.get('msg', 'invalid')}")

    @app.exception_handler(asyncpg.PostgresError)
    async def _pg_error(_r: Request, exc: asyncpg.PostgresError) -> JSONResponse:
        for kind, status, code in _PG_ERRORS:
            if isinstance(exc, kind):
                # Messages come from our own triggers/functions: safe and useful to the caller.
                return _problem(status, code, exc.args[0] if exc.args else code)
        raise exc

    # ---------------------------------------------------------------- auth
    def caller_scope(authorization: Annotated[str | None, Header()] = None) -> Scope:
        token = (authorization or "").removeprefix("Bearer ").strip()
        if token and hmac.compare_digest(token, cfg.api_token.get_secret_value()):
            return Scope.API
        if (
            token
            and cfg.worker_token
            and hmac.compare_digest(token, cfg.worker_token.get_secret_value())
        ):
            return Scope.WORKER
        raise ProblemError(401, "unauthenticated", "a valid service token is required")

    def caller(
        x_tenant_id: Annotated[uuid.UUID, Header()], x_actor_id: Annotated[uuid.UUID, Header()]
    ) -> Caller:
        return Caller(tenant_id=x_tenant_id, actor_id=x_actor_id)

    def api_only(scope: Annotated[Scope, Depends(caller_scope)]) -> None:
        if scope is not Scope.API:
            raise ProblemError(403, "scope_denied", "this operation is not allowed for workers")

    any_scope = [Depends(caller_scope)]
    api_scope = [Depends(caller_scope), Depends(api_only)]
    CallerDep = Annotated[Caller, Depends(caller)]  # noqa: N806

    def pool(request: Request) -> asyncpg.Pool:
        return request.app.state.pool  # type: ignore[no-any-return]

    PoolDep = Annotated[asyncpg.Pool, Depends(pool)]  # noqa: N806

    def ok(data: Any) -> Any:
        return service.json_ready(data)

    # ---------------------------------------------------------------- probes
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "azinco-ledger", "version": __version__}

    @app.get("/ready")
    async def ready(p: PoolDep) -> JSONResponse:
        try:
            privileged = await p.fetchval(
                "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
        except (OSError, asyncpg.PostgresError) as exc:
            return _problem(503, "not_ready", type(exc).__name__)
        if privileged is not False:
            return _problem(503, "not_ready", "ledger role must not be privileged")
        return JSONResponse({"status": "ready"})

    # ---------------------------------------------------------------- endpoints
    base = "/internal/ledger"

    @app.post(f"{base}/accounts", status_code=201, dependencies=api_scope)
    async def create_account(body: AccountIn, c: CallerDep, p: PoolDep) -> Created:
        return Created(
            id=await service.create_account(
                p,
                c,
                entity_id=body.entity_id,
                code=body.code,
                name=body.name,
                account_class=body.account_class,
                is_suspense=body.is_suspense,
                currency=body.currency,
            )
        )

    @app.post(f"{base}/periods", status_code=201, dependencies=api_scope)
    async def create_period(body: PeriodIn, c: CallerDep, p: PoolDep) -> Created:
        if body.end_date < body.start_date:
            raise ProblemError(422, "invalid_request", "end_date is before start_date")
        return Created(
            id=await service.create_period(
                p, c, entity_id=body.entity_id, start=body.start_date, end=body.end_date
            )
        )

    @app.post(f"{base}/periods/{{period_id}}/lock", status_code=204, dependencies=api_scope)
    async def lock_period(period_id: uuid.UUID, c: CallerDep, p: PoolDep) -> None:
        await service.lock_period(p, c, period_id)

    @app.post(f"{base}/periods/{{period_id}}/reopen", status_code=204, dependencies=api_scope)
    async def reopen_period(period_id: uuid.UUID, body: ReopenIn, c: CallerDep, p: PoolDep) -> None:
        await service.reopen_period(p, c, period_id, body.approval_id)

    @app.post(f"{base}/drafts", status_code=201, dependencies=any_scope)
    async def create_draft(body: DraftIn, c: CallerDep, p: PoolDep) -> Any:
        return ok(await service.create_draft(p, c, body))

    @app.post(f"{base}/post", dependencies=api_scope)
    async def post(body: PostIn, c: CallerDep, p: PoolDep) -> Any:
        return ok(await service.post_journal(p, c, body.journal_id, body.approval_id))

    @app.post(f"{base}/reverse", status_code=201, dependencies=api_scope)
    async def reverse(body: ReverseIn, c: CallerDep, p: PoolDep) -> Any:
        return ok(
            await service.create_reversal(
                p, c, body.journal_id, body.reversal_date, body.description
            )
        )

    @app.post(f"{base}/discard", dependencies=any_scope)
    async def discard(body: DiscardIn, c: CallerDep, p: PoolDep) -> Any:
        return ok(await service.discard_journal(p, c, body.journal_id, body.reason))

    @app.get(f"{base}/journals/{{journal_id}}", dependencies=any_scope)
    async def get_journal(journal_id: uuid.UUID, c: CallerDep, p: PoolDep) -> Any:
        return ok(await service.get_journal(p, c, journal_id))

    @app.get(f"{base}/verify", dependencies=any_scope)
    async def verify(c: CallerDep, p: PoolDep) -> Any:
        return ok(await service.verify_chain(p, c))

    return app
