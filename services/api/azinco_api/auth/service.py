"""Authentication use-cases. All database access goes through `tenant_session` (RLS applies)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from azinco_api.auth import mfa
from azinco_api.auth.mailer import send_mail, verification_mail
from azinco_api.auth.passwords import hash_password, validate_password, verify_password
from azinco_api.auth.rbac import mfa_required
from azinco_api.auth.tokens import hash_token, new_token
from azinco_api.core.config import Settings
from azinco_api.db.models import PlatformRole, TenantRole, UserStatus, UserType
from azinco_api.db.tenancy import tenant_session

log = structlog.get_logger("azinco.auth")

VERIFICATION_TTL = timedelta(hours=24)


class AuthError(Exception):
    """Generic authentication failure.

    The message is safe to show; it never reveals which part failed.
    """

    def __init__(self, message: str = "Invalid e-mail, password or code.", status: int = 401):
        super().__init__(message)
        self.status = status


class MfaCodeRequiredError(AuthError):
    def __init__(self) -> None:
        super().__init__("Enter the 6-digit code from your authenticator app.", 401)


@dataclass(frozen=True)
class Membership:
    tenant_id: uuid.UUID
    tenant_name: str
    role: TenantRole


@dataclass(frozen=True)
class Principal:
    """The authenticated user for one request."""

    user_id: uuid.UUID
    session_id: uuid.UUID
    email: str
    display_name: str
    user_type: UserType
    mfa_enabled: bool
    mfa_verified: bool
    memberships: tuple[Membership, ...] = field(default_factory=tuple)
    platform_roles: tuple[PlatformRole, ...] = field(default_factory=tuple)

    @property
    def mfa_required(self) -> bool:
        return mfa_required(
            self.user_type == UserType.STAFF,
            (m.role for m in self.memberships),
            self.platform_roles,
        )

    @property
    def mfa_satisfied(self) -> bool:
        return self.mfa_verified or not self.mfa_required

    def roles_in(self, tenant_id: uuid.UUID) -> tuple[TenantRole, ...]:
        return tuple(m.role for m in self.memberships if m.tenant_id == tenant_id)


@dataclass(frozen=True)
class LoginResult:
    token: str
    principal: Principal


# --------------------------------------------------------------------------- registration
async def register(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    email: str,
    password: str,
    display_name: str,
) -> None:
    """Create a pending account and send a verification e-mail.

    Always completes the same way whether or not the e-mail is already registered,
    so the endpoint cannot be used to discover accounts (no user enumeration).
    """
    validate_password(password, email)
    user_id = uuid.uuid4()
    token = new_token()
    try:
        async with tenant_session(factory, None, user_id) as s:
            await s.execute(
                text(
                    "INSERT INTO app.users (id, email, display_name, user_type, password_hash) "
                    "VALUES (:id, :email, :name, 'client', :ph)"
                ),
                {
                    "id": user_id,
                    "email": email,
                    "name": display_name,
                    "ph": hash_password(password),
                },
            )
            await s.execute(
                text(
                    "INSERT INTO app.email_verification_tokens (token_hash, user_id, expires_at) "
                    "VALUES (:h, :u, :exp)"
                ),
                {"h": hash_token(token), "u": user_id, "exp": datetime.now(UTC) + VERIFICATION_TTL},
            )
    except IntegrityError:
        log.info("auth.register.duplicate_email")  # nothing is sent; response stays identical
        return
    await send_mail(settings, verification_mail(settings, email, token))
    log.info("auth.register.created", user_id=str(user_id))


async def verify_email(factory: async_sessionmaker[AsyncSession], token: str) -> bool:
    async with tenant_session(factory, None) as s:
        user_id = await s.scalar(
            text("SELECT app.auth_consume_verification_token(:h)"), {"h": hash_token(token)}
        )
    log.info("auth.verify_email", ok=user_id is not None)
    return user_id is not None


# --------------------------------------------------------------------------- login / sessions
async def login(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    email: str,
    password: str,
    totp_code: str | None,
) -> LoginResult:
    async with tenant_session(factory, None) as s:
        row = (
            (await s.execute(text("SELECT * FROM app.auth_find_user(:e)"), {"e": email}))
            .mappings()
            .first()
        )

    password_ok = verify_password(row["password_hash"] if row else None, password)
    if row is None:
        raise AuthError()
    user_id: uuid.UUID = row["id"]
    now = datetime.now(UTC)
    if row["locked_until"] is not None and row["locked_until"] > now:
        raise AuthError("Too many failed attempts. Try again later.", 429)
    if not password_ok:
        await _record_failure(factory, settings, user_id)
        raise AuthError()
    if row["status"] != UserStatus.ACTIVE.value:
        msg = (
            "Please confirm your e-mail address first."
            if row["status"] == UserStatus.PENDING_VERIFICATION.value
            else "This account is disabled."
        )
        raise AuthError(msg, 403)

    mfa_verified = False
    if row["mfa_enabled"]:
        if not totp_code:
            raise MfaCodeRequiredError()
        secret = mfa.decrypt_secret(settings.mfa_encryption_key, row["mfa_secret_enc"])
        if not mfa.verify_code(secret, totp_code):
            await _record_failure(factory, settings, user_id)
            raise AuthError()
        mfa_verified = True

    token = new_token()
    async with tenant_session(factory, None, user_id) as s:
        await s.execute(text("SELECT app.auth_login_succeeded(:u)"), {"u": user_id})
        await s.execute(
            text(
                "INSERT INTO app.sessions (user_id, token_hash, mfa_verified, expires_at) "
                "VALUES (:u, :h, :m, :exp)"
            ),
            {
                "u": user_id,
                "h": hash_token(token),
                "m": mfa_verified,
                "exp": now + timedelta(hours=settings.session_absolute_hours),
            },
        )
    principal = await resolve_session(factory, settings, token)
    if principal is None:  # pragma: no cover - would mean the session we just made is invalid
        raise AuthError()
    log.info("auth.login.success", user_id=str(user_id), mfa=mfa_verified)
    return LoginResult(token=token, principal=principal)


async def _record_failure(
    factory: async_sessionmaker[AsyncSession], settings: Settings, user_id: uuid.UUID
) -> None:
    async with tenant_session(factory, None) as s:
        await s.execute(
            text("SELECT app.auth_login_failed(:u, :max, make_interval(mins => :mins))"),
            {
                "u": user_id,
                "max": settings.login_max_failures,
                "mins": settings.login_lockout_minutes,
            },
        )
    log.info("auth.login.failure", user_id=str(user_id))


async def resolve_session(
    factory: async_sessionmaker[AsyncSession], settings: Settings, token: str
) -> Principal | None:
    async with tenant_session(factory, None) as s:
        sess = (
            (
                await s.execute(
                    text(
                        "SELECT * FROM app.auth_resolve_session(:h, make_interval(mins => :idle))"
                    ),
                    {"h": hash_token(token), "idle": settings.session_idle_minutes},
                )
            )
            .mappings()
            .first()
        )
    if sess is None:
        return None
    user_id: uuid.UUID = sess["user_id"]
    async with tenant_session(factory, None, user_id) as s:
        user = (
            (
                await s.execute(
                    text(
                        "SELECT email, display_name, user_type, mfa_enabled FROM app.users "
                        "WHERE id = :u"
                    ),
                    {"u": user_id},
                )
            )
            .mappings()
            .one()
        )
        members = (
            (
                await s.execute(
                    text(
                        "SELECT m.tenant_id, m.role FROM app.tenant_memberships m "
                        "WHERE m.user_id = :u AND (m.expires_at IS NULL OR m.expires_at > now()) "
                        "ORDER BY m.tenant_id, m.role"
                    ),
                    {"u": user_id},
                )
            )
            .mappings()
            .all()
        )
        platform = (
            await s.scalars(
                text("SELECT role FROM app.platform_roles WHERE user_id = :u ORDER BY role"),
                {"u": user_id},
            )
        ).all()
    memberships: list[Membership] = []
    for m in members:
        async with tenant_session(factory, m["tenant_id"], user_id) as s:
            name = await s.scalar(text("SELECT name FROM app.tenants"))
        memberships.append(Membership(m["tenant_id"], str(name), TenantRole(m["role"])))
    return Principal(
        user_id=user_id,
        session_id=sess["session_id"],
        email=str(user["email"]),
        display_name=str(user["display_name"]),
        user_type=UserType(user["user_type"]),
        mfa_enabled=bool(user["mfa_enabled"]),
        mfa_verified=bool(sess["mfa_verified"]),
        memberships=tuple(memberships),
        platform_roles=tuple(PlatformRole(r) for r in platform),
    )


async def logout(factory: async_sessionmaker[AsyncSession], principal: Principal) -> None:
    async with tenant_session(factory, None, principal.user_id) as s:
        await s.execute(
            text("UPDATE app.sessions SET revoked_at = now() WHERE id = :sid"),
            {"sid": principal.session_id},
        )
    log.info("auth.logout", user_id=str(principal.user_id))


# --------------------------------------------------------------------------- MFA enrolment
@dataclass(frozen=True)
class MfaSetup:
    secret: str
    otpauth_uri: str
    qr_svg: str


async def mfa_begin(
    factory: async_sessionmaker[AsyncSession], settings: Settings, principal: Principal
) -> MfaSetup:
    if principal.mfa_enabled:
        raise AuthError("MFA is already enabled.", 409)
    secret = mfa.new_secret()
    encrypted = mfa.encrypt_secret(settings.mfa_encryption_key, secret)
    async with tenant_session(factory, None, principal.user_id) as s:
        await s.execute(
            text("UPDATE app.users SET mfa_secret_enc = :sec WHERE id = :u"),
            {"sec": encrypted, "u": principal.user_id},
        )
    uri = mfa.provisioning_uri(secret, principal.email, settings.mfa_issuer)
    return MfaSetup(secret=secret, otpauth_uri=uri, qr_svg=mfa.qr_svg(uri))


async def mfa_confirm(
    factory: async_sessionmaker[AsyncSession], settings: Settings, principal: Principal, code: str
) -> None:
    async with tenant_session(factory, None, principal.user_id) as s:
        enc = await s.scalar(
            text("SELECT mfa_secret_enc FROM app.users WHERE id = :u"), {"u": principal.user_id}
        )
        if not enc:
            raise AuthError("Start MFA setup first.", 409)
        secret = mfa.decrypt_secret(settings.mfa_encryption_key, enc)
        if not mfa.verify_code(secret, code):
            raise AuthError("That code is not valid. Check your device time and try again.", 400)
        await s.execute(
            text("UPDATE app.users SET mfa_enabled = true WHERE id = :u"), {"u": principal.user_id}
        )
        await s.execute(
            text("UPDATE app.sessions SET mfa_verified = true WHERE id = :sid"),
            {"sid": principal.session_id},
        )
    log.info("auth.mfa.enabled", user_id=str(principal.user_id))
