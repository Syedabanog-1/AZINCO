"""FastAPI dependencies: current principal, MFA enforcement, CSRF and permission checks."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from azinco_api.auth.rbac import STEP_UP_PERMISSIONS, Permission, tenant_permissions
from azinco_api.auth.service import Principal, resolve_session
from azinco_api.core.config import Settings

SESSION_COOKIE = "azinco_session"
CSRF_COOKIE = "azinco_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class ProblemHTTPException(HTTPException):
    """HTTPException carrying a machine-readable `code` for the client (RFC 9457 extension)."""

    def __init__(self, status_code: int, detail: str, code: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


async def get_optional_principal(
    request: Request,
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Principal | None:
    cached = getattr(request.state, "principal", None)
    if isinstance(cached, Principal):
        return cached
    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) > 128:
        return None
    principal = await resolve_session(factory, settings, token)
    request.state.principal = principal
    return principal


async def require_principal(
    principal: Annotated[Principal | None, Depends(get_optional_principal)],
) -> Principal:
    if principal is None:
        raise ProblemHTTPException(401, "Please sign in.", "not_authenticated")
    return principal


async def require_mfa_satisfied(
    principal: Annotated[Principal, Depends(require_principal)],
) -> Principal:
    """Staff, reviewers and platform roles must finish MFA before using anything else."""
    if not principal.mfa_satisfied:
        code = "mfa_setup_required" if not principal.mfa_enabled else "mfa_required"
        raise ProblemHTTPException(403, "Multi-factor authentication is required.", code)
    return principal


def csrf_protect(request: Request) -> None:
    """Double-submit check for state-changing requests made with a session cookie."""
    if request.method in SAFE_METHODS or SESSION_COOKIE not in request.cookies:
        return
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    if not cookie or not hmac.compare_digest(cookie, header):
        raise ProblemHTTPException(403, "Missing or invalid CSRF token.", "csrf_failed")


def require_tenant_permission(
    permission: Permission,
) -> Callable[..., Awaitable[Principal]]:
    """Dependency factory: the principal must hold `permission` in the path's `tenant_id`."""

    async def _check(
        tenant_id: uuid.UUID,
        principal: Annotated[Principal, Depends(require_mfa_satisfied)],
    ) -> Principal:
        perms = tenant_permissions(principal.roles_in(tenant_id))
        if permission not in perms:
            # 404 rather than 403: do not confirm that another tenant exists.
            raise ProblemHTTPException(404, "Not found.", "not_found")
        if permission in STEP_UP_PERMISSIONS and not principal.mfa_verified:
            raise ProblemHTTPException(
                403, "This action needs a verified MFA session.", "mfa_step_up_required"
            )
        return principal

    return _check
