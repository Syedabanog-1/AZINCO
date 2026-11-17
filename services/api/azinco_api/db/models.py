"""SQLAlchemy models for schema `app` (Blueprint Part 3 §3.3 — Tenancy & IAM).

The Alembic migrations are the source of truth for the database; `alembic check` in CI
fails if these models and the migrations drift apart.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    MetaData,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "app"

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention=NAMING_CONVENTION)


# ----------------------------------------------------------------------------- enums
class TenantStatus(enum.StrEnum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDED = "offboarded"


class FundsHandling(enum.StrEnum):
    """BS §5.3. LEDGER (Option A) is the default; SEGREGATED (Option B) stays disabled
    in the application until the Reviewer of Record and legal counsel approve it."""

    LEDGER = "ledger"
    SEGREGATED = "segregated"


class UserType(enum.StrEnum):
    CLIENT = "client"
    STAFF = "staff"
    SYSTEM = "system"


class UserStatus(enum.StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    DISABLED = "disabled"


class Locale(enum.StrEnum):
    EN = "en"
    UR = "ur"


class TenantRole(enum.StrEnum):
    """Tenant-scoped roles (Blueprint Part 1 §1.4)."""

    CLIENT_OWNER = "client_owner"
    CLIENT_STAFF = "client_staff"
    SUPPORT_OPS = "support_ops"
    REVIEWER = "reviewer"
    SECOND_REVIEWER = "second_reviewer"
    LOCAL_PARTNER = "local_partner"
    AUDITOR = "auditor"


class PlatformRole(enum.StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    AI_ENGINEER = "ai_engineer"
    COMPLIANCE_OFFICER = "compliance_officer"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        schema=SCHEMA,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,  # types are created explicitly by the migration
    )


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ----------------------------------------------------------------------------- tables
class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("home_jurisdiction ~ '^[A-Z]{2}$'", name="home_jurisdiction_iso2"),
        CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="base_currency_iso4217"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        _pg_enum(TenantStatus, "tenant_status"),
        nullable=False,
        server_default=TenantStatus.ONBOARDING.value,
    )
    home_jurisdiction: Mapped[str] = mapped_column(String(2), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="PKR")
    funds_handling: Mapped[FundsHandling] = mapped_column(
        _pg_enum(FundsHandling, "funds_handling"),
        nullable=False,
        server_default=FundsHandling.LEDGER.value,
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("position('@' in email) > 1", name="email_has_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)  # set by auth (Step 0.7)
    user_type: Mapped[UserType] = mapped_column(_pg_enum(UserType, "user_type"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        _pg_enum(UserStatus, "user_status"),
        nullable=False,
        server_default=UserStatus.PENDING_VERIFICATION.value,
    )
    locale: Mapped[Locale] = mapped_column(
        _pg_enum(Locale, "locale"), nullable=False, server_default=Locale.EN.value
    )
    mfa_enabled: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    role: Mapped[TenantRole] = mapped_column(_pg_enum(TenantRole, "tenant_role"), primary_key=True)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class PlatformRoleGrant(Base):
    __tablename__ = "platform_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[PlatformRole] = mapped_column(
        _pg_enum(PlatformRole, "platform_role"), primary_key=True
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = _created_at()
