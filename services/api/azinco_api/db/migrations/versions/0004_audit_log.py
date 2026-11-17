"""Immutable, hash-chained audit log (schema `audit`).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-17

Requirements: FR-ADM-01, NFR-SEC-04 (BS §7.3(15), §8.2, §12). ADR-0012.

Design
------
* One append-only table `audit.audit_events`. Each tenant has its own stream; events without a
  tenant (e.g. login of a user, platform actions) go to the platform stream.
* Every event stores `prev_hash` and `row_hash = sha256(prev_hash || canonical_text(event))`, with a
  gap-free `seq` per stream. Changing, deleting or re-ordering any past event breaks the chain,
  which `audit.verify_chain()` detects.
* Writes only through `audit.append_event(...)` (SECURITY DEFINER): it takes a per-stream advisory
  lock, so concurrent writers cannot fork the chain. No runtime role has INSERT, UPDATE or DELETE.
* Triggers reject UPDATE, DELETE and TRUNCATE for everyone, including the owner.
* Reading is tenant-scoped by Row-Level Security, like schema `app`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

A = "audit"
PLATFORM_STREAM = "00000000-0000-0000-0000-000000000000"
WRITERS = "azinco_app, azinco_worker, azinco_ledger, azinco_audit"
READERS = "azinco_app, azinco_readonly, azinco_audit"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA {A}")
    op.execute(f"REVOKE ALL ON SCHEMA {A} FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA {A} TO {WRITERS}, azinco_readonly")

    op.execute(f"CREATE TYPE {A}.actor_type AS ENUM ('human', 'agent', 'system')")
    op.execute(
        f"""
        CREATE TABLE {A}.audit_events (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            stream_id     uuid        NOT NULL,
            seq           bigint      NOT NULL CHECK (seq >= 1),
            tenant_id     uuid        NULL,
            occurred_at   timestamptz NOT NULL,
            actor_type    {A}.actor_type NOT NULL,
            actor_id      uuid        NULL,
            action        text        NOT NULL CHECK (action ~ '^[a-z][a-z0-9_.]{{2,99}}$'),
            resource_type text        NULL,
            resource_id   text        NULL,
            request_id    text        NULL,
            details       jsonb       NOT NULL DEFAULT '{{}}'::jsonb,
            prev_hash     bytea       NOT NULL CHECK (octet_length(prev_hash) = 32),
            row_hash      bytea       NOT NULL CHECK (octet_length(row_hash) = 32),
            CONSTRAINT uq_audit_stream_seq UNIQUE (stream_id, seq),
            CONSTRAINT ck_audit_stream_matches_tenant
                CHECK (stream_id = COALESCE(tenant_id, '{PLATFORM_STREAM}'::uuid))
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_audit_events_tenant_time ON {A}.audit_events (tenant_id, occurred_at)"
    )
    op.execute(f"CREATE INDEX ix_audit_events_actor ON {A}.audit_events (actor_id)")

    # ------------------------------------------------------------------ immutability
    op.execute(
        f"""
        CREATE FUNCTION {A}.reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only (% rejected)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER trg_audit_no_update_delete BEFORE UPDATE OR DELETE ON {A}.audit_events "
        f"FOR EACH ROW EXECUTE FUNCTION {A}.reject_change()"
    )
    op.execute(
        f"CREATE TRIGGER trg_audit_no_truncate BEFORE TRUNCATE ON {A}.audit_events "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {A}.reject_change()"
    )

    # ------------------------------------------------------------------ canonical form & hash
    op.execute(
        f"""
        CREATE FUNCTION {A}.canonical_text(
            p_stream uuid, p_seq bigint, p_tenant uuid, p_occurred timestamptz,
            p_actor_type {A}.actor_type, p_actor uuid, p_action text, p_resource_type text,
            p_resource_id text, p_request_id text, p_details jsonb
        ) RETURNS text LANGUAGE sql IMMUTABLE AS $$
            SELECT concat_ws('|',
                p_stream::text, p_seq::text, COALESCE(p_tenant::text, ''),
                to_char(p_occurred AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                p_actor_type::text, COALESCE(p_actor::text, ''), p_action,
                COALESCE(p_resource_type, ''), COALESCE(p_resource_id, ''),
                COALESCE(p_request_id, ''), p_details::text)
        $$
        """
    )

    # ------------------------------------------------------------------ append
    op.execute(
        f"""
        CREATE FUNCTION {A}.append_event(
            p_tenant uuid, p_actor_type {A}.actor_type, p_actor uuid, p_action text,
            p_resource_type text, p_resource_id text, p_request_id text, p_details jsonb
        ) RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, {A}
        AS $$
        DECLARE
            v_stream uuid := COALESCE(p_tenant, '{PLATFORM_STREAM}'::uuid);
            v_prev   bytea;
            v_seq    bigint;
            v_now    timestamptz := clock_timestamp();
            v_hash   bytea;
            v_id     bigint;
        BEGIN
            -- One writer per stream at a time: the chain can never fork.
            PERFORM pg_advisory_xact_lock(hashtextextended('audit:' || v_stream::text, 0));
            SELECT e.row_hash, e.seq INTO v_prev, v_seq
              FROM {A}.audit_events e
             WHERE e.stream_id = v_stream
             ORDER BY e.seq DESC LIMIT 1;
            v_prev := COALESCE(v_prev, decode(repeat('00', 32), 'hex'));
            v_seq  := COALESCE(v_seq, 0) + 1;
            v_hash := digest(v_prev || convert_to({A}.canonical_text(
                          v_stream, v_seq, p_tenant, v_now, p_actor_type, p_actor, p_action,
                          p_resource_type, p_resource_id, p_request_id,
                          COALESCE(p_details, '{{}}'::jsonb)), 'UTF8'), 'sha256');
            INSERT INTO {A}.audit_events (stream_id, seq, tenant_id, occurred_at, actor_type,
                    actor_id, action, resource_type, resource_id, request_id, details,
                    prev_hash, row_hash)
            VALUES (v_stream, v_seq, p_tenant, v_now, p_actor_type, p_actor, p_action,
                    p_resource_type, p_resource_id, p_request_id,
                    COALESCE(p_details, '{{}}'::jsonb), v_prev, v_hash)
            RETURNING id INTO v_id;
            RETURN v_id;
        END $$
        """
    )

    # ------------------------------------------------------------------ verify
    op.execute(
        f"""
        CREATE FUNCTION {A}.verify_chain(p_tenant uuid)
        RETURNS TABLE (events bigint, ok boolean, first_bad_seq bigint)
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, {A}
        AS $$
        DECLARE
            v_stream uuid := COALESCE(p_tenant, '{PLATFORM_STREAM}'::uuid);
            v_prev   bytea := decode(repeat('00', 32), 'hex');
            v_expect bigint := 1;
            v_count  bigint := 0;
            r        record;
        BEGIN
            FOR r IN SELECT * FROM {A}.audit_events e WHERE e.stream_id = v_stream ORDER BY e.seq
            LOOP
                v_count := v_count + 1;
                IF r.seq <> v_expect OR r.prev_hash <> v_prev OR r.row_hash <> digest(
                       v_prev || convert_to({A}.canonical_text(
                           r.stream_id, r.seq, r.tenant_id, r.occurred_at, r.actor_type,
                           r.actor_id, r.action, r.resource_type, r.resource_id,
                           r.request_id, r.details), 'UTF8'), 'sha256') THEN
                    events := v_count; ok := false; first_bad_seq := r.seq;
                    RETURN NEXT; RETURN;
                END IF;
                v_prev := r.row_hash;
                v_expect := v_expect + 1;
            END LOOP;
            events := v_count; ok := true; first_bad_seq := NULL;
            RETURN NEXT;
        END $$
        """
    )

    # ------------------------------------------------------------------ privileges & RLS
    op.execute(f"REVOKE ALL ON {A}.audit_events FROM PUBLIC")
    op.execute(f"GRANT SELECT ON {A}.audit_events TO {READERS}")
    for fn in (
        "append_event(uuid, audit.actor_type, uuid, text, text, text, text, jsonb)",
        "verify_chain(uuid)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {A}.{fn} FROM PUBLIC")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION {A}.append_event(uuid, audit.actor_type, uuid, text, text, "
        f"text, text, jsonb) TO {WRITERS}"
    )
    op.execute(f"GRANT EXECUTE ON FUNCTION {A}.verify_chain(uuid) TO {READERS}")

    op.execute(f"ALTER TABLE {A}.audit_events ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {A}.audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY audit_tenant_read ON {A}.audit_events FOR SELECT "
        f"USING (tenant_id IS NOT NULL AND tenant_id = app.current_tenant_id())"
    )
    # The definer functions (owned by azinco_migrator) must see whole streams.
    op.execute(
        f"CREATE POLICY audit_definer_read ON {A}.audit_events FOR SELECT "
        f"TO azinco_migrator USING (true)"
    )
    op.execute(
        f"CREATE POLICY audit_definer_insert ON {A}.audit_events FOR INSERT "
        f"TO azinco_migrator WITH CHECK (true)"
    )


def downgrade() -> None:
    # Dropping the audit trail is deliberately a manual, explicit operation.
    op.execute(f"DROP SCHEMA {A} CASCADE")
