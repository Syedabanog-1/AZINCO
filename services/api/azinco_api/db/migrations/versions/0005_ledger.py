"""Ledger foundation: entities, chart of accounts, periods, approvals, journals (schema `ledger`).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-18

Requirements: FR-LED-03, FR-LED-04, FR-LED-05, FR-LED-09, FR-LED-15, FR-REV approvals
(Base Standard §6.4, §6.5, §8.2, §8.4, §8.7). Architecture invariants L1-L9 (blueprint §2.8).

Every invariant is enforced by the database, so a bug in any service cannot persist a wrong book:

L1  Balanced. A deferred constraint trigger checks at COMMIT that every journal has >= 2 lines and
    Σ base_debit = Σ base_credit (base = entity functional currency, PKR by default). When all lines
    share one currency the transaction amounts must balance too.
L2  Posted is immutable. Lines can never be updated or deleted; journals change only through the
    ledger functions below (posting / reversal / discard), guarded by a trigger.
L3  Corrections by reversal only: a reversal mirrors every line, links `reverses_id` (unique), and
    marks the original `reversed` when it is posted.
L4  Evidence: every line has an `evidence_type`; `extraction` lines need document + field ids; a
    line with a tax code needs the rule version that produced it.
L5  Periods: posting needs an `open` or `reopened` period covering the journal date; periods of
    one entity never overlap; reopening a locked period needs a reviewer approval.
L6  Human approver: posting needs an approval row whose approver is an active, MFA-enabled human
    with the reviewer / second_reviewer role in that tenant. Agents can never approve. Each
    approval can be used exactly once.
L7  Money: NUMERIC(20,4) amounts, NUMERIC(20,10) FX rates, ISO currency codes; base amounts must
    equal round(amount * fx_rate, 4), and functional-currency lines must use fx_rate = 1.
L8  Tenant scoped: RLS (ENABLE + FORCE) on every table, composite FKs carry tenant_id.
L9  Tamper evident: posted journals form a per-tenant hash chain; `ledger.verify_chain()`.

Only `azinco_ledger` (the Ledger Service) can write: it may INSERT accounts, periods, draft
journals and their lines, and call the functions. `azinco_app` inserts approvals (the reviewer
action) and entities. Other runtime roles read only.

[Recommended] choices beyond the Base Standard: status `discarded` for abandoned drafts (drafts
are never deleted), single-use approvals table, `btree_gist` exclusion for period overlap.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "app"
L = "ledger"
READERS = "azinco_app, azinco_worker, azinco_audit, azinco_readonly"
ZERO_HASH = "decode(repeat('00', 32), 'hex')"
DEFINER = "SECURITY DEFINER SET search_path = pg_catalog, public, app, ledger"

LEDGER_TABLES = ("accounts", "periods", "journals", "journal_lines", "consumed_approvals")


def _rls(schema: str, table: str) -> None:
    op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_isolation ON {schema}.{table} FOR ALL "
        f"USING (tenant_id = {S}.current_tenant_id()) "
        f"WITH CHECK (tenant_id = {S}.current_tenant_id())"
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(f"CREATE SCHEMA {L}")
    op.execute(f"REVOKE ALL ON SCHEMA {L} FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA {L} TO azinco_ledger, {READERS}")
    op.execute(f"GRANT USAGE ON SCHEMA {S} TO azinco_ledger")

    # ------------------------------------------------------------------ enums
    op.execute(
        f"CREATE TYPE {L}.account_class AS ENUM "
        "('asset', 'liability', 'equity', 'revenue', 'cogs', 'opex', 'other', 'tax')"
    )
    op.execute(f"CREATE TYPE {L}.period_status AS ENUM ('open', 'locked', 'reopened')")
    op.execute(
        f"CREATE TYPE {L}.journal_status AS ENUM ('draft', 'posted', 'reversed', 'discarded')"
    )
    op.execute(f"CREATE TYPE {L}.journal_source AS ENUM ('agent', 'manual', 'opening', 'reversal')")
    op.execute(
        f"CREATE TYPE {L}.evidence_type AS ENUM "
        "('extraction', 'manual_with_approval', 'opening', 'system_calc')"
    )
    op.execute(f"CREATE TYPE {S}.approval_subject AS ENUM ('journal_post', 'period_reopen')")

    # ------------------------------------------------------------------ entities (app)
    op.execute(
        f"""
        CREATE TABLE {S}.entities (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           uuid NOT NULL REFERENCES {S}.tenants(id),
            legal_name          text NOT NULL CHECK (length(btrim(legal_name)) > 0),
            jurisdiction        char(2) NOT NULL CHECK (jurisdiction ~ '^[A-Z]{{2}}$'),
            functional_currency char(3) NOT NULL DEFAULT 'PKR'
                                CHECK (functional_currency ~ '^[A-Z]{{3}}$'),
            created_at          timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_entities_tenant_id UNIQUE (tenant_id, id)
        )
        """
    )
    _rls(S, "entities")
    op.execute(f"GRANT SELECT, INSERT ON {S}.entities TO azinco_app")
    op.execute(f"GRANT SELECT ON {S}.entities TO azinco_ledger, azinco_worker, azinco_readonly")
    # The definer functions need to read users/memberships for approver checks.
    op.execute(f"GRANT SELECT ON {S}.tenant_memberships TO azinco_ledger")

    # ------------------------------------------------------------------ approvals (app)
    op.execute(
        f"""
        CREATE TABLE {S}.approvals (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES {S}.tenants(id),
            subject_type   {S}.approval_subject NOT NULL,
            subject_id     uuid NOT NULL,
            approver_id    uuid NOT NULL REFERENCES {S}.users(id),
            approver_role  {S}.tenant_role NOT NULL,
            approver_name  text NOT NULL,
            licence_status text NOT NULL DEFAULT 'not_recorded'
                           CHECK (licence_status IN ('verified', 'pending', 'not_recorded')),
            comment        text NULL,
            decided_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT uq_approvals_tenant_id UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_approvals_subject ON {S}.approvals (tenant_id, subject_type, subject_id)"
    )
    _rls(S, "approvals")
    op.execute(f"GRANT SELECT, INSERT ON {S}.approvals TO azinco_app")
    op.execute(f"GRANT SELECT ON {S}.approvals TO azinco_ledger, azinco_audit, azinco_readonly")
    op.execute(
        f"""
        CREATE FUNCTION {S}.approval_guard() RETURNS trigger LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            v_user record;
            v_role {S}.tenant_role;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'approvals are immutable (% rejected)', TG_OP
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            -- The approver is always the signed-in human in context: nobody approves for another.
            IF NEW.approver_id IS DISTINCT FROM {S}.current_user_id() THEN
                RAISE EXCEPTION 'approver must be the current user'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT u.user_type, u.status, u.mfa_enabled, u.display_name INTO v_user
              FROM {S}.users u WHERE u.id = NEW.approver_id;
            IF NOT FOUND OR v_user.user_type = 'system' OR v_user.status <> 'active'
               OR NOT v_user.mfa_enabled THEN
                RAISE EXCEPTION 'approver must be an active human with MFA enabled'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT m.role INTO v_role FROM {S}.tenant_memberships m
             WHERE m.tenant_id = NEW.tenant_id AND m.user_id = NEW.approver_id
               AND m.role IN ('reviewer', 'second_reviewer')
               AND (m.expires_at IS NULL OR m.expires_at > now())
             ORDER BY m.role LIMIT 1;
            IF v_role IS NULL THEN
                RAISE EXCEPTION 'approver needs the reviewer role in this tenant'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            NEW.approver_role := v_role;          -- snapshots: cannot be forged by the caller
            NEW.approver_name := v_user.display_name;
            NEW.decided_at    := clock_timestamp();
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER trg_approvals_guard BEFORE INSERT OR UPDATE OR DELETE ON {S}.approvals "
        f"FOR EACH ROW EXECUTE FUNCTION {S}.approval_guard()"
    )

    # ------------------------------------------------------------------ accounts
    op.execute(
        f"""
        CREATE TABLE {L}.accounts (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL,
            entity_id   uuid NOT NULL,
            code        text NOT NULL CHECK (code ~ '^[0-9A-Za-z][0-9A-Za-z.\\-]{{0,19}}$'),
            name        text NOT NULL CHECK (length(btrim(name)) > 0),
            class       {L}.account_class NOT NULL,
            is_suspense boolean NOT NULL DEFAULT false,
            currency    char(3) NULL CHECK (currency ~ '^[A-Z]{{3}}$'),
            active      boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_accounts_entity FOREIGN KEY (tenant_id, entity_id)
                REFERENCES {S}.entities (tenant_id, id),
            CONSTRAINT uq_accounts_entity_code UNIQUE (entity_id, code),
            CONSTRAINT uq_accounts_scope UNIQUE (tenant_id, entity_id, id)
        )
        """
    )

    # ------------------------------------------------------------------ periods
    op.execute(
        f"""
        CREATE TABLE {L}.periods (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id  uuid NOT NULL,
            entity_id  uuid NOT NULL,
            start_date date NOT NULL,
            end_date   date NOT NULL,
            status     {L}.period_status NOT NULL DEFAULT 'open',
            locked_at  timestamptz NULL,
            locked_by  uuid NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_periods_range CHECK (end_date >= start_date),
            CONSTRAINT fk_periods_entity FOREIGN KEY (tenant_id, entity_id)
                REFERENCES {S}.entities (tenant_id, id),
            CONSTRAINT ex_periods_no_overlap EXCLUDE USING gist
                (entity_id WITH =, daterange(start_date, end_date, '[]') WITH &&)
        )
        """
    )

    # ------------------------------------------------------------------ journals
    op.execute(
        f"""
        CREATE TABLE {L}.journals (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL,
            entity_id    uuid NOT NULL,
            journal_date date NOT NULL,
            description  text NOT NULL CHECK (length(btrim(description)) > 0),
            status       {L}.journal_status NOT NULL DEFAULT 'draft',
            source       {L}.journal_source NOT NULL,
            reverses_id  uuid NULL UNIQUE REFERENCES {L}.journals(id),
            created_by   uuid NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            -- set by ledger.post_journal only
            period_id    uuid NULL REFERENCES {L}.periods(id),
            approval_id  uuid NULL UNIQUE REFERENCES {S}.approvals(id),
            journal_no   bigint NULL,
            ledger_seq   bigint NULL,
            prev_hash    bytea NULL CHECK (octet_length(prev_hash) = 32),
            row_hash     bytea NULL CHECK (octet_length(row_hash) = 32),
            posted_at    timestamptz NULL,
            CONSTRAINT fk_journals_entity FOREIGN KEY (tenant_id, entity_id)
                REFERENCES {S}.entities (tenant_id, id),
            CONSTRAINT uq_journals_scope UNIQUE (tenant_id, entity_id, id),
            CONSTRAINT uq_journals_seq UNIQUE (tenant_id, ledger_seq),
            CONSTRAINT uq_journals_no UNIQUE (entity_id, journal_no),
            CONSTRAINT ck_journals_reversal_link
                CHECK ((source = 'reversal') = (reverses_id IS NOT NULL)),
            CONSTRAINT ck_journals_posted_fields CHECK (
                (status IN ('draft', 'discarded')
                    AND approval_id IS NULL AND ledger_seq IS NULL AND posted_at IS NULL)
                OR (status IN ('posted', 'reversed')
                    AND period_id IS NOT NULL AND approval_id IS NOT NULL
                    AND journal_no IS NOT NULL AND ledger_seq IS NOT NULL
                    AND prev_hash IS NOT NULL AND row_hash IS NOT NULL
                    AND posted_at IS NOT NULL))
        )
        """
    )
    op.execute(f"CREATE INDEX ix_journals_entity_date ON {L}.journals (entity_id, journal_date)")

    # ------------------------------------------------------------------ journal lines
    op.execute(
        f"""
        CREATE TABLE {L}.journal_lines (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           uuid NOT NULL,
            entity_id           uuid NOT NULL,
            journal_id          uuid NOT NULL,
            line_no             integer NOT NULL CHECK (line_no >= 1),
            account_id          uuid NOT NULL,
            debit               numeric(20,4) NOT NULL DEFAULT 0,
            credit              numeric(20,4) NOT NULL DEFAULT 0,
            currency            char(3) NOT NULL CHECK (currency ~ '^[A-Z]{{3}}$'),
            fx_rate             numeric(20,10) NOT NULL DEFAULT 1 CHECK (fx_rate > 0),
            base_debit          numeric(20,4) NOT NULL DEFAULT 0,
            base_credit         numeric(20,4) NOT NULL DEFAULT 0,
            evidence_type       {L}.evidence_type NOT NULL,
            document_id         uuid NULL,
            extraction_field_id uuid NULL,
            rule_version_id     uuid NULL,
            tax_code            text NULL,
            memo                text NULL,
            CONSTRAINT uq_lines_no UNIQUE (journal_id, line_no),
            CONSTRAINT fk_lines_journal FOREIGN KEY (tenant_id, entity_id, journal_id)
                REFERENCES {L}.journals (tenant_id, entity_id, id),
            CONSTRAINT fk_lines_account FOREIGN KEY (tenant_id, entity_id, account_id)
                REFERENCES {L}.accounts (tenant_id, entity_id, id),
            CONSTRAINT ck_lines_one_side
                CHECK (debit >= 0 AND credit >= 0 AND ((debit = 0) <> (credit = 0))),
            CONSTRAINT ck_lines_base_matches CHECK (
                base_debit = round(debit * fx_rate, 4)
                AND base_credit = round(credit * fx_rate, 4)),
            CONSTRAINT ck_lines_extraction_evidence CHECK (
                evidence_type <> 'extraction'
                OR (document_id IS NOT NULL AND extraction_field_id IS NOT NULL)),
            CONSTRAINT ck_lines_tax_rule CHECK (tax_code IS NULL OR rule_version_id IS NOT NULL)
        )
        """
    )
    op.execute(f"CREATE INDEX ix_lines_account ON {L}.journal_lines (account_id)")

    # Approvals can be used once (journal posting or period reopening).
    op.execute(
        f"""
        CREATE TABLE {L}.consumed_approvals (
            approval_id uuid PRIMARY KEY REFERENCES {S}.approvals(id),
            tenant_id   uuid NOT NULL,
            used_for    uuid NOT NULL,
            used_at     timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )

    _ledger_triggers()
    _ledger_functions()

    # ------------------------------------------------------------------ privileges & RLS
    for table in LEDGER_TABLES:
        op.execute(f"REVOKE ALL ON {L}.{table} FROM PUBLIC")
        op.execute(f"GRANT SELECT ON {L}.{table} TO azinco_ledger, {READERS}")
        _rls(L, table)
        # Definer functions (owner azinco_migrator) read whole rows by id, then check tenant.
        op.execute(
            f"CREATE POLICY {table}_definer_read ON {L}.{table} FOR SELECT "
            f"TO azinco_migrator USING (true)"
        )
    op.execute(f"GRANT INSERT ON {L}.accounts, {L}.periods TO azinco_ledger")
    op.execute(f"GRANT UPDATE (name, active) ON {L}.accounts TO azinco_ledger")
    op.execute(f"GRANT INSERT ON {L}.journals, {L}.journal_lines TO azinco_ledger")


def _ledger_triggers() -> None:
    # ---- accounts: code/class/scope never change (history would silently move) --------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.account_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (NEW.tenant_id, NEW.entity_id, NEW.code, NEW.class, NEW.is_suspense)
               IS DISTINCT FROM (OLD.tenant_id, OLD.entity_id, OLD.code, OLD.class, OLD.is_suspense)
            THEN
                RAISE EXCEPTION 'account code, class and scope are fixed once created'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER trg_accounts_guard BEFORE UPDATE ON {L}.accounts "
        f"FOR EACH ROW EXECUTE FUNCTION {L}.account_guard()"
    )

    # ---- immutable rows: lines always, journals/periods outside the ledger functions -------
    op.execute(
        f"""
        CREATE FUNCTION {L}.reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% on %.% is not allowed: the ledger is append-only',
                TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in ("journal_lines", "consumed_approvals"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {L}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION {L}.reject_change()"
        )
    for table in ("accounts", "periods", "journals", "journal_lines", "consumed_approvals"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON {L}.{table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION {L}.reject_change()"
        )
    op.execute(
        f"CREATE TRIGGER trg_periods_no_delete BEFORE DELETE ON {L}.periods "
        f"FOR EACH ROW EXECUTE FUNCTION {L}.reject_change()"
    )
    op.execute(
        f"CREATE TRIGGER trg_accounts_no_delete BEFORE DELETE ON {L}.accounts "
        f"FOR EACH ROW EXECUTE FUNCTION {L}.reject_change()"
    )

    # ---- journals: legal state transitions only, and only inside ledger functions ----------
    op.execute(
        f"""
        CREATE FUNCTION {L}.journal_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'journals are never deleted (discard a draft instead)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'draft' THEN
                    RAISE EXCEPTION 'journals are created as drafts'
                        USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END IF;
            IF current_setting('ledger.in_function', true) IS DISTINCT FROM 'on' THEN
                RAISE EXCEPTION 'journals change only through ledger functions'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            -- Identity and content never change, whatever the status.
            IF (NEW.id, NEW.tenant_id, NEW.entity_id, NEW.journal_date, NEW.description,
                NEW.source, NEW.reverses_id, NEW.created_by, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.tenant_id, OLD.entity_id, OLD.journal_date, OLD.description,
                OLD.source, OLD.reverses_id, OLD.created_by, OLD.created_at) THEN
                RAISE EXCEPTION 'journal content is immutable'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT ((OLD.status = 'draft' AND NEW.status IN ('posted', 'discarded'))
                    OR (OLD.status = 'posted' AND NEW.status = 'reversed')) THEN
                RAISE EXCEPTION 'illegal journal transition % -> %', OLD.status, NEW.status
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.status = 'posted' AND (NEW.period_id, NEW.approval_id, NEW.journal_no,
                    NEW.ledger_seq, NEW.prev_hash, NEW.row_hash, NEW.posted_at)
                IS DISTINCT FROM (OLD.period_id, OLD.approval_id, OLD.journal_no,
                    OLD.ledger_seq, OLD.prev_hash, OLD.row_hash, OLD.posted_at) THEN
                RAISE EXCEPTION 'posted journal fields are immutable'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER trg_journals_guard BEFORE INSERT OR UPDATE OR DELETE ON {L}.journals "
        f"FOR EACH ROW EXECUTE FUNCTION {L}.journal_guard()"
    )

    # ---- periods: status changes only inside ledger functions ------------------------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.period_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'open' THEN
                    RAISE EXCEPTION 'periods are created open' USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END IF;
            IF current_setting('ledger.in_function', true) IS DISTINCT FROM 'on'
               OR (NEW.id, NEW.tenant_id, NEW.entity_id, NEW.start_date, NEW.end_date)
                  IS DISTINCT FROM (OLD.id, OLD.tenant_id, OLD.entity_id, OLD.start_date,
                                    OLD.end_date) THEN
                RAISE EXCEPTION 'periods change only through lock/reopen'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER trg_periods_guard BEFORE INSERT OR UPDATE ON {L}.periods "
        f"FOR EACH ROW EXECUTE FUNCTION {L}.period_guard()"
    )

    # ---- lines: only on drafts; functional currency uses rate 1 ---------------------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.line_guard() RETURNS trigger LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            v_status {L}.journal_status;
            v_fc char(3);
        BEGIN
            SELECT j.status INTO v_status FROM {L}.journals j WHERE j.id = NEW.journal_id;
            IF v_status IS DISTINCT FROM 'draft'
               AND current_setting('ledger.in_function', true) IS DISTINCT FROM 'on' THEN
                RAISE EXCEPTION 'lines can only be added to draft journals'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT e.functional_currency INTO v_fc FROM {S}.entities e WHERE e.id = NEW.entity_id;
            IF NEW.currency = v_fc AND NEW.fx_rate <> 1 THEN
                RAISE EXCEPTION 'functional-currency lines must use fx_rate 1'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER trg_lines_guard BEFORE INSERT ON {L}.journal_lines "
        f"FOR EACH ROW EXECUTE FUNCTION {L}.line_guard()"
    )

    # ---- L1: balance, checked at COMMIT for every journal touched in the transaction --------
    op.execute(
        f"""
        CREATE FUNCTION {L}.assert_balanced(p_journal uuid) RETURNS void
        LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            r record;
        BEGIN
            SELECT count(*) AS n,
                   COALESCE(sum(base_debit), 0) AS bd, COALESCE(sum(base_credit), 0) AS bc,
                   COALESCE(sum(debit), 0) AS d, COALESCE(sum(credit), 0) AS c,
                   count(DISTINCT currency) AS currencies
              INTO r FROM {L}.journal_lines WHERE journal_id = p_journal;
            IF r.n < 2 THEN
                RAISE EXCEPTION 'journal % needs at least two lines', p_journal
                    USING ERRCODE = 'check_violation';
            END IF;
            IF r.bd <> r.bc THEN
                RAISE EXCEPTION 'journal % is unbalanced: base debit % <> base credit %',
                    p_journal, r.bd, r.bc USING ERRCODE = 'check_violation';
            END IF;
            IF r.currencies = 1 AND r.d <> r.c THEN
                RAISE EXCEPTION 'journal % is unbalanced: debit % <> credit %', p_journal, r.d, r.c
                    USING ERRCODE = 'check_violation';
            END IF;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {L}.lines_balanced_trigger() RETURNS trigger
        LANGUAGE plpgsql {DEFINER} AS $$
        BEGIN
            PERFORM {L}.assert_balanced(NEW.journal_id);
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {L}.journal_has_lines_trigger() RETURNS trigger
        LANGUAGE plpgsql {DEFINER} AS $$
        BEGIN
            PERFORM {L}.assert_balanced(NEW.id);
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        f"CREATE CONSTRAINT TRIGGER trg_lines_balanced AFTER INSERT ON {L}.journal_lines "
        f"DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        f"EXECUTE FUNCTION {L}.lines_balanced_trigger()"
    )
    op.execute(
        f"CREATE CONSTRAINT TRIGGER trg_journals_have_lines AFTER INSERT ON {L}.journals "
        f"DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        f"EXECUTE FUNCTION {L}.journal_has_lines_trigger()"
    )


def _ledger_functions() -> None:
    # ---- canonical text of a posted journal, lines in order ---------------------------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.canonical_text(
            p_journal uuid, p_seq bigint, p_no bigint, p_approval uuid, p_period uuid,
            p_posted_at timestamptz
        ) RETURNS text
        LANGUAGE sql STABLE {DEFINER} AS $$
            -- Posting fields are parameters so the hash is computed before the row is written.
            SELECT concat_ws('|', j.tenant_id::text, j.entity_id::text, p_seq::text,
                       p_no::text, j.id::text, j.journal_date::text, j.description,
                       j.source::text, COALESCE(j.reverses_id::text, ''), p_approval::text,
                       p_period::text,
                       to_char(p_posted_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))
                   || '#' ||
                   COALESCE((SELECT string_agg(concat_ws('|', l.line_no::text, l.account_id::text,
                                l.debit::text, l.credit::text, l.currency, l.fx_rate::text,
                                l.base_debit::text, l.base_credit::text, l.evidence_type::text,
                                COALESCE(l.document_id::text, ''),
                                COALESCE(l.extraction_field_id::text, ''),
                                COALESCE(l.rule_version_id::text, ''),
                                COALESCE(l.tax_code, ''), COALESCE(l.memo, '')),
                                ';' ORDER BY l.line_no)
                             FROM {L}.journal_lines l WHERE l.journal_id = j.id), '')
              FROM {L}.journals j WHERE j.id = p_journal
        $$
        """
    )

    # ---- helpers -----------------------------------------------------------------------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.require_tenant(p_tenant uuid) RETURNS void
        LANGUAGE plpgsql STABLE AS $$
        BEGIN
            IF p_tenant IS NULL OR p_tenant IS DISTINCT FROM {S}.current_tenant_id() THEN
                RAISE EXCEPTION 'not found' USING ERRCODE = 'no_data_found';
            END IF;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {L}.consume_approval(
            p_approval uuid, p_tenant uuid, p_subject {S}.approval_subject, p_subject_id uuid
        ) RETURNS {S}.approvals LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            v {S}.approvals;
        BEGIN
            SELECT * INTO v FROM {S}.approvals a WHERE a.id = p_approval;
            IF NOT FOUND OR v.tenant_id <> p_tenant OR v.subject_type <> p_subject
               OR v.subject_id <> p_subject_id THEN
                RAISE EXCEPTION 'approval does not authorise this action'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            INSERT INTO {L}.consumed_approvals (approval_id, tenant_id, used_for)
            VALUES (p_approval, p_tenant, p_subject_id);  -- PK: second use fails
            RETURN v;
        END $$
        """
    )

    # ---- post ----------------------------------------------------------------------------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.post_journal(p_journal uuid, p_approval uuid) RETURNS bigint
        LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            j {L}.journals;
            v_appr {S}.approvals;
            v_period uuid;
            v_prev bytea;
            v_seq bigint;
            v_no bigint;
            v_at timestamptz := clock_timestamp();
        BEGIN
            SELECT * INTO j FROM {L}.journals WHERE id = p_journal FOR UPDATE;
            PERFORM {L}.require_tenant(j.tenant_id);
            IF j.status <> 'draft' THEN
                RAISE EXCEPTION 'only drafts can be posted (status %)', j.status
                    USING ERRCODE = 'check_violation';
            END IF;
            PERFORM {L}.assert_balanced(j.id);
            v_appr := {L}.consume_approval(p_approval, j.tenant_id, 'journal_post', j.id);

            SELECT p.id INTO v_period FROM {L}.periods p
             WHERE p.entity_id = j.entity_id AND j.journal_date BETWEEN p.start_date AND p.end_date
               AND p.status IN ('open', 'reopened');
            IF v_period IS NULL THEN
                RAISE EXCEPTION 'no open period for % on %', j.entity_id, j.journal_date
                    USING ERRCODE = 'check_violation';
            END IF;

            IF j.source = 'reversal' THEN
                PERFORM 1 FROM {L}.journals o
                 WHERE o.id = j.reverses_id AND o.status = 'posted' FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'the journal being reversed is not posted'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;

            -- One writer per tenant ledger: the hash chain and numbering can never fork.
            PERFORM pg_advisory_xact_lock(hashtextextended('ledger:' || j.tenant_id::text, 0));
            SELECT x.row_hash, x.ledger_seq INTO v_prev, v_seq FROM {L}.journals x
             WHERE x.tenant_id = j.tenant_id AND x.ledger_seq IS NOT NULL
             ORDER BY x.ledger_seq DESC LIMIT 1;
            v_prev := COALESCE(v_prev, {ZERO_HASH});
            v_seq := COALESCE(v_seq, 0) + 1;
            SELECT COALESCE(max(x.journal_no), 0) + 1 INTO v_no FROM {L}.journals x
             WHERE x.entity_id = j.entity_id;

            PERFORM set_config('ledger.in_function', 'on', true);
            UPDATE {L}.journals SET status = 'posted', period_id = v_period,
                   approval_id = p_approval, journal_no = v_no, ledger_seq = v_seq,
                   prev_hash = v_prev, posted_at = v_at,
                   row_hash = digest(v_prev || convert_to({L}.canonical_text(
                       j.id, v_seq, v_no, p_approval, v_period, v_at), 'UTF8'), 'sha256')
             WHERE id = j.id;
            IF j.source = 'reversal' THEN
                UPDATE {L}.journals SET status = 'reversed' WHERE id = j.reverses_id;
            END IF;
            PERFORM set_config('ledger.in_function', 'off', true);

            PERFORM audit.append_event(j.tenant_id, 'system', v_appr.approver_id,
                'ledger.journal.posted', 'journal', j.id::text, NULL,
                jsonb_build_object('journal_no', v_no, 'ledger_seq', v_seq,
                                   'approval_id', p_approval, 'source', j.source));
            RETURN v_seq;
        END $$
        """
    )

    # ---- reverse: create a mirrored draft (it is posted with its own approval) ---------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.create_reversal(
            p_journal uuid, p_date date, p_description text, p_created_by uuid
        ) RETURNS uuid LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            j {L}.journals;
            v_id uuid := gen_random_uuid();
        BEGIN
            SELECT * INTO j FROM {L}.journals WHERE id = p_journal;
            PERFORM {L}.require_tenant(j.tenant_id);
            IF j.status <> 'posted' THEN
                RAISE EXCEPTION 'only posted journals can be reversed (status %)', j.status
                    USING ERRCODE = 'check_violation';
            END IF;
            INSERT INTO {L}.journals (id, tenant_id, entity_id, journal_date, description,
                                      source, reverses_id, created_by)
            VALUES (v_id, j.tenant_id, j.entity_id, p_date, p_description, 'reversal', j.id,
                    p_created_by);
            INSERT INTO {L}.journal_lines (tenant_id, entity_id, journal_id, line_no, account_id,
                    debit, credit, currency, fx_rate, base_debit, base_credit, evidence_type,
                    document_id, extraction_field_id, rule_version_id, tax_code, memo)
            SELECT l.tenant_id, l.entity_id, v_id, l.line_no, l.account_id,
                   l.credit, l.debit, l.currency, l.fx_rate, l.base_credit, l.base_debit,
                   l.evidence_type, l.document_id, l.extraction_field_id, l.rule_version_id,
                   l.tax_code, l.memo
              FROM {L}.journal_lines l WHERE l.journal_id = j.id;
            PERFORM audit.append_event(j.tenant_id, 'system', p_created_by,
                'ledger.journal.reversal_drafted', 'journal', v_id::text, NULL,
                jsonb_build_object('reverses', j.id));
            RETURN v_id;
        END $$
        """
    )

    # ---- discard a draft -------------------------------------------------------------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.discard_journal(p_journal uuid, p_reason text) RETURNS void
        LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            j {L}.journals;
        BEGIN
            SELECT * INTO j FROM {L}.journals WHERE id = p_journal FOR UPDATE;
            PERFORM {L}.require_tenant(j.tenant_id);
            PERFORM set_config('ledger.in_function', 'on', true);
            UPDATE {L}.journals SET status = 'discarded' WHERE id = j.id;  -- guard checks draft
            PERFORM set_config('ledger.in_function', 'off', true);
            PERFORM audit.append_event(j.tenant_id, 'system', {S}.current_user_id(),
                'ledger.journal.discarded', 'journal', j.id::text, NULL,
                jsonb_build_object('reason', p_reason));
        END $$
        """
    )

    # ---- periods: lock and reopen ------------------------------------------------------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.lock_period(p_period uuid) RETURNS void
        LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            p {L}.periods;
        BEGIN
            SELECT * INTO p FROM {L}.periods WHERE id = p_period FOR UPDATE;
            PERFORM {L}.require_tenant(p.tenant_id);
            IF p.status = 'locked' THEN
                RAISE EXCEPTION 'period already locked' USING ERRCODE = 'check_violation';
            END IF;
            PERFORM set_config('ledger.in_function', 'on', true);
            UPDATE {L}.periods SET status = 'locked', locked_at = clock_timestamp(),
                   locked_by = {S}.current_user_id() WHERE id = p.id;
            PERFORM set_config('ledger.in_function', 'off', true);
            PERFORM audit.append_event(p.tenant_id, 'system', {S}.current_user_id(),
                'ledger.period.locked', 'period', p.id::text, NULL,
                jsonb_build_object('start', p.start_date, 'end', p.end_date));
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {L}.reopen_period(p_period uuid, p_approval uuid) RETURNS void
        LANGUAGE plpgsql {DEFINER} AS $$
        DECLARE
            p {L}.periods;
            v_appr {S}.approvals;
        BEGIN
            SELECT * INTO p FROM {L}.periods WHERE id = p_period FOR UPDATE;
            PERFORM {L}.require_tenant(p.tenant_id);
            IF p.status <> 'locked' THEN
                RAISE EXCEPTION 'only locked periods can be reopened'
                    USING ERRCODE = 'check_violation';
            END IF;
            v_appr := {L}.consume_approval(p_approval, p.tenant_id, 'period_reopen', p.id);
            PERFORM set_config('ledger.in_function', 'on', true);
            UPDATE {L}.periods SET status = 'reopened' WHERE id = p.id;
            PERFORM set_config('ledger.in_function', 'off', true);
            PERFORM audit.append_event(p.tenant_id, 'system', v_appr.approver_id,
                'ledger.period.reopened', 'period', p.id::text, NULL,
                jsonb_build_object('approval_id', p_approval));
        END $$
        """
    )

    # ---- verify the per-tenant chain -----------------------------------------------------------
    op.execute(
        f"""
        CREATE FUNCTION {L}.verify_chain(p_tenant uuid)
        RETURNS TABLE (journals bigint, ok boolean, first_bad_seq bigint)
        LANGUAGE plpgsql STABLE {DEFINER} AS $$
        DECLARE
            v_prev bytea := {ZERO_HASH};
            v_expect bigint := 1;
            v_count bigint := 0;
            r record;
        BEGIN
            -- Tenants verify their own chain; the database superuser (ops) may verify any.
            IF p_tenant IS DISTINCT FROM {S}.current_tenant_id()
               AND NOT (SELECT rolsuper FROM pg_roles WHERE rolname = session_user) THEN
                RAISE EXCEPTION 'not found' USING ERRCODE = 'no_data_found';
            END IF;
            FOR r IN SELECT x.id, x.ledger_seq, x.prev_hash, x.row_hash, x.journal_no,
                            x.approval_id, x.period_id, x.posted_at FROM {L}.journals x
                      WHERE x.tenant_id = p_tenant AND x.ledger_seq IS NOT NULL
                      ORDER BY x.ledger_seq
            LOOP
                v_count := v_count + 1;
                IF r.ledger_seq <> v_expect OR r.prev_hash <> v_prev OR r.row_hash <> digest(
                       v_prev || convert_to({L}.canonical_text(r.id, r.ledger_seq, r.journal_no,
                           r.approval_id, r.period_id, r.posted_at), 'UTF8'), 'sha256') THEN
                    journals := v_count; ok := false; first_bad_seq := r.ledger_seq;
                    RETURN NEXT; RETURN;
                END IF;
                v_prev := r.row_hash;
                v_expect := v_expect + 1;
            END LOOP;
            journals := v_count; ok := true; first_bad_seq := NULL;
            RETURN NEXT;
        END $$
        """
    )

    for fn in (
        "post_journal(uuid, uuid)",
        "create_reversal(uuid, date, text, uuid)",
        "discard_journal(uuid, text)",
        "lock_period(uuid)",
        "reopen_period(uuid, uuid)",
        "verify_chain(uuid)",
        "canonical_text(uuid, bigint, bigint, uuid, uuid, timestamptz)",
        "assert_balanced(uuid)",
        "consume_approval(uuid, uuid, app.approval_subject, uuid)",
        "require_tenant(uuid)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {L}.{fn} FROM PUBLIC")
    for fn in (
        "post_journal(uuid, uuid)",
        "create_reversal(uuid, date, text, uuid)",
        "discard_journal(uuid, text)",
        "lock_period(uuid)",
        "reopen_period(uuid, uuid)",
    ):
        op.execute(f"GRANT EXECUTE ON FUNCTION {L}.{fn} TO azinco_ledger")
    op.execute(f"GRANT EXECUTE ON FUNCTION {L}.verify_chain(uuid) TO azinco_ledger, {READERS}")


def downgrade() -> None:
    op.execute(f"DROP SCHEMA {L} CASCADE")
    op.execute(f"DROP TABLE {S}.approvals")
    op.execute(f"DROP FUNCTION {S}.approval_guard()")
    op.execute(f"DROP TABLE {S}.entities")
    op.execute(f"DROP TYPE {S}.approval_subject")
    op.execute(f"REVOKE SELECT ON {S}.tenant_memberships FROM azinco_ledger")
    op.execute(f"REVOKE USAGE ON SCHEMA {S} FROM azinco_ledger")
