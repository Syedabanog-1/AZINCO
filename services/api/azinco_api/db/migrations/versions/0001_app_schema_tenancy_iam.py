"""Schema `app`: tenancy and IAM tables with least-privilege grants.

Revision ID: 0001
Revises:
Create Date: 2026-11-17

Requirements: FR-IAM-02, FR-IAM-03, FR-ONB-10, NFR-SEC-01 (BS §4.1, §5.3, §8.4, §12).
Row-Level Security is added in revision 0002 (Step 0.6).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "app"
RUNTIME_ROLES = ("azinco_app", "azinco_worker", "azinco_ledger", "azinco_audit", "azinco_readonly")

ENUMS: dict[str, tuple[str, ...]] = {
    "tenant_status": ("onboarding", "active", "suspended", "offboarded"),
    "funds_handling": ("ledger", "segregated"),
    "user_type": ("client", "staff", "system"),
    "user_status": ("pending_verification", "active", "disabled"),
    "locale": ("en", "ur"),
    "tenant_role": (
        "client_owner",
        "client_staff",
        "support_ops",
        "reviewer",
        "second_reviewer",
        "local_partner",
        "auditor",
    ),
    "platform_role": ("platform_admin", "ai_engineer", "compliance_officer"),
}


def _enum(name: str) -> pg.ENUM:
    return pg.ENUM(*ENUMS[name], name=name, schema=S, create_type=False)


def _ts(name: str) -> sa.Column[datetime]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {S}")
    op.execute(f"REVOKE ALL ON SCHEMA {S} FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA {S} TO {', '.join(RUNTIME_ROLES)}")

    for name, values in ENUMS.items():
        pg.ENUM(*values, name=name, schema=S).create(op.get_bind(), checkfirst=False)

    op.create_table(
        "tenants",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", _enum("tenant_status"), nullable=False, server_default="onboarding"),
        sa.Column("home_jurisdiction", sa.String(2), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="PKR"),
        sa.Column(
            "funds_handling", _enum("funds_handling"), nullable=False, server_default="ledger"
        ),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("home_jurisdiction ~ '^[A-Z]{2}$'", name="home_jurisdiction_iso2"),
        sa.CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="base_currency_iso4217"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        schema=S,
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", pg.CITEXT(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("user_type", _enum("user_type"), nullable=False),
        sa.Column(
            "status", _enum("user_status"), nullable=False, server_default="pending_verification"
        ),
        sa.Column("locale", _enum("locale"), nullable=False, server_default="en"),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("email"),
        sa.CheckConstraint("position('@' in email) > 1", name="email_has_at"),
        schema=S,
    )

    op.create_table(
        "tenant_memberships",
        sa.Column(
            "tenant_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{S}.tenants.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{S}.users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("role", _enum("tenant_role"), primary_key=True),
        sa.Column(
            "granted_by",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{S}.users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        schema=S,
    )
    op.create_index(
        op.f("ix_tenant_memberships_user_id"), "tenant_memberships", ["user_id"], schema=S
    )

    op.create_table(
        "platform_roles",
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{S}.users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("role", _enum("platform_role"), primary_key=True),
        sa.Column(
            "granted_by",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{S}.users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        _ts("created_at"),
        schema=S,
    )

    # updated_at maintained by the database, not by application code.
    op.execute(
        f"""
        CREATE FUNCTION {S}.touch_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END $$
        """
    )
    for table in ("tenants", "users"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_touch BEFORE UPDATE ON {S}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION {S}.touch_updated_at()"
        )

    # Least privilege (Blueprint Part 3 §3.1). No role gets DELETE: removal is a governed
    # process (offboarding / retention, BS §9.7), not an ad-hoc statement.
    tables = ("tenants", "users", "tenant_memberships", "platform_roles")
    for table in tables:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.{table} TO azinco_app")
        op.execute(f"GRANT SELECT ON {S}.{table} TO azinco_worker, azinco_readonly")


def downgrade() -> None:
    op.drop_table("platform_roles", schema=S)
    op.drop_index(op.f("ix_tenant_memberships_user_id"), table_name="tenant_memberships", schema=S)
    op.drop_table("tenant_memberships", schema=S)
    op.drop_table("users", schema=S)
    op.drop_table("tenants", schema=S)
    op.execute(f"DROP FUNCTION IF EXISTS {S}.touch_updated_at()")
    for name in reversed(list(ENUMS)):
        pg.ENUM(name=name, schema=S).drop(op.get_bind(), checkfirst=True)
    op.execute(f"DROP SCHEMA IF EXISTS {S}")
