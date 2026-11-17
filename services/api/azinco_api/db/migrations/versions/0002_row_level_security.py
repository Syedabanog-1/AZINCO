"""Row-Level Security for schema `app` (tenant isolation).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17

Requirements: NFR-SEC-01, FR-IAM-02 (BS §8.4, §12, §14 "data leak between clients").

How it works
------------
* Every request runs in a transaction that first calls
  set_config('app.tenant_id', <uuid>, true) and set_config('app.user_id', <uuid>, true).
  `true` = transaction-local, so a pooled connection never carries context to the next request.
* Policies compare rows with app.current_tenant_id() / app.current_user_id().
  With no context those functions return NULL, and NULL never matches: zero rows, writes refused.
* RLS is ENABLEd and FORCEd, so even the table owner (azinco_migrator) is subject to it.
  No runtime role has BYPASSRLS (verified by verify_stack.py).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "app"
TABLES = ("tenants", "users", "tenant_memberships", "platform_roles")


def upgrade() -> None:
    # Context helpers. A malformed value raises (22P02) instead of silently matching nothing.
    op.execute(
        f"""
        CREATE FUNCTION {S}.current_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {S}.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {S}.current_tenant_id() FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {S}.current_user_id() FROM PUBLIC")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION {S}.current_tenant_id(), {S}.current_user_id() "
        "TO azinco_app, azinco_worker, azinco_ledger, azinco_audit, azinco_readonly"
    )

    # Membership check used by the users policy. SECURITY DEFINER so it can read memberships
    # without recursing into RLS; it only answers yes/no for the current context.
    op.execute(
        f"""
        CREATE FUNCTION {S}.is_member_of_current_tenant(p_user_id uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, {S}
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM {S}.tenant_memberships m
                WHERE m.user_id = p_user_id
                  AND m.tenant_id = {S}.current_tenant_id()
                  AND (m.expires_at IS NULL OR m.expires_at > now())
            )
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {S}.is_member_of_current_tenant(uuid) FROM PUBLIC")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION {S}.is_member_of_current_tenant(uuid) "
        "TO azinco_app, azinco_worker, azinco_readonly"
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")

    # tenants: only the tenant in context. A new tenant is created by setting its
    # (application-generated) id as context first, then inserting it.
    op.execute(
        f"CREATE POLICY tenants_isolation ON {S}.tenants FOR ALL "
        f"USING (id = {S}.current_tenant_id()) "
        f"WITH CHECK (id = {S}.current_tenant_id())"
    )

    # tenant_memberships: rows of the tenant in context.
    op.execute(
        f"CREATE POLICY memberships_isolation ON {S}.tenant_memberships FOR ALL "
        f"USING (tenant_id = {S}.current_tenant_id()) "
        f"WITH CHECK (tenant_id = {S}.current_tenant_id())"
    )

    # users are platform-level identities. Visible: yourself, or members of the tenant in
    # context. Writable: only your own row (registration sets app.user_id to the new id).
    op.execute(
        f"CREATE POLICY users_read ON {S}.users FOR SELECT "
        f"USING (id = {S}.current_user_id() OR {S}.is_member_of_current_tenant(id))"
    )
    op.execute(
        f"CREATE POLICY users_insert_self ON {S}.users FOR INSERT "
        f"WITH CHECK (id = {S}.current_user_id())"
    )
    op.execute(
        f"CREATE POLICY users_update_self ON {S}.users FOR UPDATE "
        f"USING (id = {S}.current_user_id()) WITH CHECK (id = {S}.current_user_id())"
    )

    # platform_roles: a user may read their own platform roles. Granting roles is an
    # administrative path added with the Admin console (no runtime INSERT policy yet).
    op.execute(
        f"CREATE POLICY platform_roles_read_own ON {S}.platform_roles FOR SELECT "
        f"USING (user_id = {S}.current_user_id())"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS platform_roles_read_own ON {S}.platform_roles")
    op.execute(f"DROP POLICY IF EXISTS users_update_self ON {S}.users")
    op.execute(f"DROP POLICY IF EXISTS users_insert_self ON {S}.users")
    op.execute(f"DROP POLICY IF EXISTS users_read ON {S}.users")
    op.execute(f"DROP POLICY IF EXISTS memberships_isolation ON {S}.tenant_memberships")
    op.execute(f"DROP POLICY IF EXISTS tenants_isolation ON {S}.tenants")
    for table in TABLES:
        op.execute(f"ALTER TABLE {S}.{table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} DISABLE ROW LEVEL SECURITY")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.is_member_of_current_tenant(uuid)")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.current_user_id()")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.current_tenant_id()")
