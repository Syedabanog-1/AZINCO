"""Authentication: sessions, e-mail verification, lockout columns, auth functions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-17

Requirements: FR-IAM-01, FR-IAM-03, FR-IAM-04, FR-IAM-07, NFR-SEC-03 (BS §12). ADR-0006 (option a).

Design notes
------------
* Login happens before any user/tenant context exists, but RLS hides users without context.
  The few pre-context operations (find user by e-mail, record failure/success, resolve a
  session token, consume a verification token) are SECURITY DEFINER functions owned by
  `azinco_migrator`. Because RLS is FORCEd on the owner too, explicit policies `TO azinco_migrator`
  let only those functions (and migrations) see the needed rows. The app role can only EXECUTE
  the functions; it never gets broader read access.
* Session and verification tokens are stored as SHA-256 hashes, never in clear text.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "app"
DEFINER = "LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, app"
FUNCTIONS = (
    "auth_find_user(citext)",
    "auth_login_failed(uuid, integer, interval)",
    "auth_login_succeeded(uuid)",
    "auth_resolve_session(bytea, interval)",
    "auth_consume_verification_token(bytea)",
)


def upgrade() -> None:
    # ------------------------------------------------------------------ users: auth columns
    op.add_column("users", sa.Column("mfa_secret_enc", sa.Text(), nullable=True), schema=S)
    op.add_column(
        "users",
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        schema=S,
    )
    op.add_column(
        "users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True), schema=S
    )
    op.add_column(
        "users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True), schema=S
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        schema=S,
    )

    # ------------------------------------------------------------------ sessions
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{S}.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("token_hash", pg.BYTEA(), nullable=False),
        sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash"),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="token_hash_sha256"),
        schema=S,
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], schema=S)

    # ------------------------------------------------------------------ e-mail verification
    op.create_table(
        "email_verification_tokens",
        sa.Column("token_hash", pg.BYTEA(), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{S}.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="token_hash_sha256"),
        schema=S,
    )

    for table in ("sessions", "email_verification_tokens"):
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")

    # ------------------------------------------------------------------ grants
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.sessions TO azinco_app")
    op.execute(f"GRANT INSERT ON {S}.email_verification_tokens TO azinco_app")

    # ------------------------------------------------------------------ runtime policies
    op.execute(
        f"CREATE POLICY sessions_own ON {S}.sessions FOR ALL "
        f"USING (user_id = {S}.current_user_id()) "
        f"WITH CHECK (user_id = {S}.current_user_id())"
    )
    op.execute(
        f"CREATE POLICY verification_insert_own ON {S}.email_verification_tokens FOR INSERT "
        f"WITH CHECK (user_id = {S}.current_user_id())"
    )
    # A user may list their own memberships across tenants (for "choose workspace" / GET /me).
    op.execute(
        f"CREATE POLICY memberships_read_own ON {S}.tenant_memberships FOR SELECT "
        f"USING (user_id = {S}.current_user_id())"
    )

    # ------------------------------------------------------------------ definer-only policies
    for table, cmd in (
        ("users", "SELECT"),
        ("users", "UPDATE"),
        ("sessions", "SELECT"),
        ("sessions", "UPDATE"),
        ("email_verification_tokens", "SELECT"),
        ("email_verification_tokens", "UPDATE"),
    ):
        op.execute(
            f"CREATE POLICY {table}_auth_{cmd.lower()} ON {S}.{table} FOR {cmd} "
            f"TO azinco_migrator USING (true)" + (" WITH CHECK (true)" if cmd == "UPDATE" else "")
        )

    # ------------------------------------------------------------------ auth functions
    op.execute(
        f"""
        CREATE FUNCTION {S}.auth_find_user(p_email citext)
        RETURNS TABLE (id uuid, password_hash text, status {S}.user_status,
                       user_type {S}.user_type, mfa_enabled boolean, mfa_secret_enc text,
                       locked_until timestamptz)
        {DEFINER} STABLE AS $$
        BEGIN
            RETURN QUERY
            SELECT u.id, u.password_hash, u.status, u.user_type, u.mfa_enabled,
                   u.mfa_secret_enc, u.locked_until
            FROM {S}.users u WHERE u.email = p_email;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {S}.auth_login_failed(p_user uuid, p_max integer, p_lock interval)
        RETURNS void {DEFINER} AS $$
        BEGIN
            UPDATE {S}.users
               SET failed_login_count = failed_login_count + 1,
                   locked_until = CASE WHEN failed_login_count + 1 >= p_max
                                       THEN now() + p_lock ELSE locked_until END
             WHERE id = p_user;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {S}.auth_login_succeeded(p_user uuid)
        RETURNS void {DEFINER} AS $$
        BEGIN
            UPDATE {S}.users
               SET failed_login_count = 0, locked_until = NULL, last_login_at = now()
             WHERE id = p_user;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {S}.auth_resolve_session(p_token_hash bytea, p_idle interval)
        RETURNS TABLE (session_id uuid, user_id uuid, mfa_verified boolean)
        {DEFINER} AS $$
        BEGIN
            RETURN QUERY
            UPDATE {S}.sessions s
               SET last_seen_at = now()
             WHERE s.token_hash = p_token_hash
               AND s.revoked_at IS NULL
               AND s.expires_at > now()
               AND s.last_seen_at > now() - p_idle
               AND EXISTS (SELECT 1 FROM {S}.users u
                            WHERE u.id = s.user_id AND u.status = 'active')
            RETURNING s.id, s.user_id, s.mfa_verified;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {S}.auth_consume_verification_token(p_token_hash bytea)
        RETURNS uuid {DEFINER} AS $$
        DECLARE v_user uuid;
        BEGIN
            UPDATE {S}.email_verification_tokens t
               SET used_at = now()
             WHERE t.token_hash = p_token_hash AND t.used_at IS NULL AND t.expires_at > now()
            RETURNING t.user_id INTO v_user;
            IF v_user IS NULL THEN
                RETURN NULL;
            END IF;
            UPDATE {S}.users
               SET status = 'active', email_verified_at = now()
             WHERE id = v_user AND status = 'pending_verification';
            RETURN v_user;
        END $$
        """
    )
    for fn in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {S}.{fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {S}.{fn} TO azinco_app")


def downgrade() -> None:
    for fn in FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS {S}.{fn}")
    for table, cmd in (
        ("users", "select"),
        ("users", "update"),
        ("sessions", "select"),
        ("sessions", "update"),
        ("email_verification_tokens", "select"),
        ("email_verification_tokens", "update"),
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_auth_{cmd} ON {S}.{table}")
    op.execute(f"DROP POLICY IF EXISTS memberships_read_own ON {S}.tenant_memberships")
    op.drop_table("email_verification_tokens", schema=S)
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions", schema=S)
    op.drop_table("sessions", schema=S)
    for col in (
        "email_verified_at",
        "last_login_at",
        "locked_until",
        "failed_login_count",
        "mfa_secret_enc",
    ):
        op.drop_column("users", col, schema=S)
