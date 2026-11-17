"""/api/v1 authentication and identity endpoints."""

from __future__ import annotations

import secrets
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from azinco_api.auth import service
from azinco_api.auth.deps import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    ProblemHTTPException,
    csrf_protect,
    get_session_factory,
    get_settings_dep,
    require_mfa_satisfied,
    require_principal,
    require_tenant_permission,
)
from azinco_api.auth.passwords import MAX_LENGTH, PasswordPolicyError
from azinco_api.auth.rbac import Permission, platform_permissions, tenant_permissions
from azinco_api.auth.service import AuthError, MfaCodeRequiredError, Principal
from azinco_api.core.config import Settings
from azinco_api.db.tenancy import tenant_session

router = APIRouter(prefix="/api/v1", tags=["auth"])

Factory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


# --------------------------------------------------------------------------- schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_LENGTH)
    display_name: str = Field(min_length=1, max_length=100)


class AcceptedResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    message: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_LENGTH)
    code: str | None = Field(default=None, max_length=10)


class MembershipOut(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    role: str
    permissions: list[str]


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    user_type: str
    mfa_enabled: bool
    mfa_required: bool
    mfa_satisfied: bool
    memberships: list[MembershipOut]
    platform_roles: list[str]
    platform_permissions: list[str]


class MfaSetupResponse(BaseModel):
    otpauth_uri: str
    secret: str
    qr_svg: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=10)


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    home_jurisdiction: str
    base_currency: str
    funds_handling: str


def _me(p: Principal) -> MeResponse:
    return MeResponse(
        id=p.user_id,
        email=p.email,
        display_name=p.display_name,
        user_type=p.user_type.value,
        mfa_enabled=p.mfa_enabled,
        mfa_required=p.mfa_required,
        mfa_satisfied=p.mfa_satisfied,
        memberships=[
            MembershipOut(
                tenant_id=m.tenant_id,
                tenant_name=m.tenant_name,
                role=m.role.value,
                permissions=sorted(p.value for p in tenant_permissions([m.role])),
            )
            for m in p.memberships
        ],
        platform_roles=[r.value for r in p.platform_roles],
        platform_permissions=sorted(x.value for x in platform_permissions(p.platform_roles)),
    )


def _set_session_cookies(response: Response, settings: Settings, token: str) -> None:
    max_age = settings.session_absolute_hours * 3600
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    # Readable by the web app's JavaScript, which echoes it in X-CSRF-Token (double submit).
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(24),
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="strict")


def _raise(err: AuthError) -> None:
    code = "mfa_code_required" if isinstance(err, MfaCodeRequiredError) else "auth_failed"
    raise ProblemHTTPException(err.status, str(err), code) from err


# --------------------------------------------------------------------------- endpoints
@router.post("/auth/register", status_code=202, response_model=AcceptedResponse)
async def register(
    body: RegisterRequest, factory: Factory, settings: SettingsDep
) -> AcceptedResponse:
    try:
        await service.register(
            factory,
            settings,
            email=str(body.email),
            password=body.password,
            display_name=body.display_name.strip(),
        )
    except PasswordPolicyError as exc:
        raise ProblemHTTPException(422, str(exc), "weak_password") from exc
    return AcceptedResponse(
        message="If this e-mail can be registered, a confirmation link has been sent to it."
    )


@router.post("/auth/verify-email", response_model=AcceptedResponse)
async def verify_email(body: VerifyEmailRequest, factory: Factory) -> AcceptedResponse:
    if not await service.verify_email(factory, body.token):
        raise ProblemHTTPException(400, "This link is invalid or has expired.", "invalid_token")
    return AcceptedResponse(message="E-mail confirmed. You can now sign in.")


@router.post("/auth/login", response_model=MeResponse)
async def login(
    body: LoginRequest, response: Response, factory: Factory, settings: SettingsDep
) -> MeResponse:
    try:
        result = await service.login(
            factory, settings, email=str(body.email), password=body.password, totp_code=body.code
        )
    except AuthError as err:
        _raise(err)
        raise  # unreachable; keeps type checkers satisfied
    _set_session_cookies(response, settings, result.token)
    return _me(result.principal)


@router.post("/auth/logout", status_code=204, dependencies=[Depends(csrf_protect)])
async def logout(
    response: Response,
    factory: Factory,
    settings: SettingsDep,
    principal: Annotated[Principal, Depends(require_principal)],
) -> Response:
    await service.logout(factory, principal)
    _clear_session_cookies(response, settings)
    response.status_code = 204
    return response


@router.get("/me", response_model=MeResponse)
async def me(principal: Annotated[Principal, Depends(require_principal)]) -> MeResponse:
    # Available before MFA so the UI can show "set up MFA" to staff.
    return _me(principal)


@router.post(
    "/auth/mfa/setup", response_model=MfaSetupResponse, dependencies=[Depends(csrf_protect)]
)
async def mfa_setup(
    factory: Factory,
    settings: SettingsDep,
    principal: Annotated[Principal, Depends(require_principal)],
) -> MfaSetupResponse:
    try:
        setup = await service.mfa_begin(factory, settings, principal)
    except AuthError as err:
        _raise(err)
        raise
    return MfaSetupResponse(otpauth_uri=setup.otpauth_uri, secret=setup.secret, qr_svg=setup.qr_svg)


@router.post("/auth/mfa/confirm", status_code=204, dependencies=[Depends(csrf_protect)])
async def mfa_confirm(
    body: MfaConfirmRequest,
    factory: Factory,
    settings: SettingsDep,
    principal: Annotated[Principal, Depends(require_principal)],
) -> Response:
    try:
        await service.mfa_confirm(factory, settings, principal, body.code)
    except AuthError as err:
        _raise(err)
        raise
    return Response(status_code=204)


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: uuid.UUID,
    factory: Factory,
    principal: Annotated[Principal, Depends(require_tenant_permission(Permission.TENANT_READ))],
) -> TenantOut:
    """Example of the full chain: session → MFA policy → RBAC → RLS-scoped query."""
    async with tenant_session(factory, tenant_id, principal.user_id) as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT id, name, status, home_jurisdiction, base_currency, "
                        "funds_handling FROM app.tenants WHERE id = :t"
                    ),
                    {"t": tenant_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise ProblemHTTPException(404, "Not found.", "not_found")
    return TenantOut(
        id=row["id"],
        name=str(row["name"]),
        status=str(row["status"]),
        home_jurisdiction=str(row["home_jurisdiction"]),
        base_currency=str(row["base_currency"]),
        funds_handling=str(row["funds_handling"]),
    )


__all__ = ["require_mfa_satisfied", "router"]
