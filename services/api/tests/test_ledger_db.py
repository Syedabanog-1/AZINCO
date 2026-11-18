"""Step 0.9a — ledger invariants L1-L9 enforced by PostgreSQL (migration 0005).

The Ledger Service (Step 0.9b) will check the same rules in code; these tests prove the database
refuses wrong books even when the calling code is buggy. Property tests (Hypothesis) show that no
unbalanced journal and no edited posted journal can persist.

World setup uses the bootstrap superuser (test fixture only). Every ledger operation runs as the
real runtime role `azinco_ledger`, approvals as `azinco_app`, both inside tenant context.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import asyncpg
import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

from tests.db_helpers import DB_INTEGRATION, connect

pytestmark = [pytest.mark.integration, DB_INTEGRATION]

CENT = Decimal("0.0001")


# ============================================================================ connections
async def _superuser() -> asyncpg.Connection:
    user = os.environ.get("POSTGRES_SUPERUSER")
    if not user:
        pytest.skip("POSTGRES_SUPERUSER not provided")
    return await connect(user, os.environ.get("POSTGRES_SUPERUSER_PASSWORD", "unused"))


async def _ledger() -> asyncpg.Connection:
    password = os.environ.get("AZINCO_DB_LEDGER_PASSWORD")
    if not password:
        pytest.skip("AZINCO_DB_LEDGER_PASSWORD not provided")
    return await connect("azinco_ledger", password)


async def _ctx(conn: asyncpg.Connection, tenant: uuid.UUID, user: uuid.UUID | None = None) -> None:
    await conn.execute(
        "SELECT set_config('app.tenant_id', $1, true), set_config('app.user_id', $2, true)",
        str(tenant),
        str(user) if user else "",
    )


# ============================================================================ world
@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    entity: uuid.UUID
    reviewer: uuid.UUID
    reviewer_no_mfa: uuid.UUID
    client: uuid.UUID
    agent: uuid.UUID
    cash: uuid.UUID
    revenue: uuid.UUID
    expense: uuid.UUID
    period: uuid.UUID


async def _make_world(su: asyncpg.Connection, functional: str = "PKR") -> World:
    t, e = uuid.uuid4(), uuid.uuid4()
    tag = t.hex[:8]
    await su.execute(
        "INSERT INTO app.tenants (id, name, home_jurisdiction) "
        "VALUES ($1, 'Synthetic Books', 'PK')",
        t,
    )

    async def user(kind: str, user_type: str, mfa: bool, role: str | None) -> uuid.UUID:
        uid = uuid.uuid4()
        await su.execute(
            "INSERT INTO app.users (id, email, display_name, user_type, status, mfa_enabled) "
            "VALUES ($1, $2, $3, $4, 'active', $5)",
            uid,
            f"{kind}-{tag}@example.com",
            f"{kind} {tag}",
            user_type,
            mfa,
        )
        if role:
            await su.execute(
                "INSERT INTO app.tenant_memberships (tenant_id, user_id, role) VALUES ($1,$2,$3)",
                t,
                uid,
                role,
            )
        return uid

    reviewer = await user("reviewer", "staff", True, "reviewer")
    no_mfa = await user("reviewer-nomfa", "staff", False, "reviewer")
    client = await user("client", "client", True, "client_owner")
    agent = await user("agent", "system", True, "reviewer")  # even with the role: never approves
    await su.execute(
        "INSERT INTO app.entities (id, tenant_id, legal_name, jurisdiction, functional_currency) "
        "VALUES ($1, $2, 'Synthetic Traders (Pvt) Ltd', 'PK', $3)",
        e,
        t,
        functional,
    )
    accounts = {}
    for code, name, cls in (
        ("1000", "Cash", "asset"),
        ("4000", "Sales", "revenue"),
        ("6000", "Rent", "opex"),
    ):
        accounts[code] = await su.fetchval(
            "INSERT INTO ledger.accounts (tenant_id, entity_id, code, name, class) "
            "VALUES ($1,$2,$3,$4,$5) RETURNING id",
            t,
            e,
            code,
            name,
            cls,
        )
    period = await su.fetchval(
        "INSERT INTO ledger.periods (tenant_id, entity_id, start_date, end_date) "
        "VALUES ($1, $2, '2026-01-01', '2026-12-31') RETURNING id",
        t,
        e,
    )
    return World(
        t,
        e,
        reviewer,
        no_mfa,
        client,
        agent,
        accounts["1000"],
        accounts["4000"],
        accounts["6000"],
        period,
    )


@pytest.fixture
async def world() -> AsyncIterator[World]:
    su = await _superuser()
    try:
        yield await _make_world(su)
    finally:
        await su.close()


# ============================================================================ operations
Line = tuple[uuid.UUID, Decimal, Decimal]  # account, debit, credit (functional currency)


async def draft(
    w: World,
    lines: list[Line],
    *,
    when: date = date(2026, 3, 31),
    extra: list[dict[str, Any]] | None = None,
) -> uuid.UUID:
    """Insert a draft journal and its lines in ONE transaction, as the Ledger Service does."""
    conn = await _ledger()
    try:
        async with conn.transaction():
            await _ctx(conn, w.tenant, w.agent)
            jid = await conn.fetchval(
                "INSERT INTO ledger.journals (tenant_id, entity_id, journal_date, description, "
                "source, created_by) VALUES ($1,$2,$3,'Synthetic sale','agent',$4) RETURNING id",
                w.tenant,
                w.entity,
                when,
                w.agent,
            )
            rows = [
                {
                    "account": a,
                    "debit": d,
                    "credit": c,
                    "currency": "PKR",
                    "fx": Decimal(1),
                    "bd": d,
                    "bc": c,
                }
                for a, d, c in lines
            ] + (extra or [])
            for no, r in enumerate(rows, start=1):
                await conn.execute(
                    "INSERT INTO ledger.journal_lines (tenant_id, entity_id, journal_id, line_no, "
                    "account_id, debit, credit, currency, fx_rate, base_debit, base_credit, "
                    "evidence_type) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'system_calc')",
                    w.tenant,
                    w.entity,
                    jid,
                    no,
                    r["account"],
                    r["debit"],
                    r["credit"],
                    r["currency"],
                    r["fx"],
                    r["bd"],
                    r["bc"],
                )
        return uuid.UUID(str(jid))
    finally:
        await conn.close()


async def approve(
    w: World,
    subject: uuid.UUID,
    *,
    by: uuid.UUID | None = None,
    kind: str = "journal_post",
    claimed: uuid.UUID | None = None,
) -> uuid.UUID:
    """The reviewer's action through the API role (azinco_app), signed in as `by`."""
    by = by or w.reviewer
    conn = await connect()
    try:
        async with conn.transaction():
            await _ctx(conn, w.tenant, by)
            return await conn.fetchval(  # type: ignore[no-any-return]
                "INSERT INTO app.approvals (tenant_id, subject_type, subject_id, approver_id, "
                "approver_role, approver_name) VALUES ($1, $2, $3, $4, 'client_owner', 'forged') "
                "RETURNING id",
                w.tenant,
                kind,
                subject,
                claimed or by,
            )
    finally:
        await conn.close()


async def ledger_call(w: World, sql: str, *args: object) -> Any:
    conn = await _ledger()
    try:
        async with conn.transaction():
            await _ctx(conn, w.tenant, w.reviewer)
            return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


async def post(w: World, journal: uuid.UUID, approval: uuid.UUID) -> int:
    return int(await ledger_call(w, "SELECT ledger.post_journal($1, $2)", journal, approval))


async def verify(w: World) -> asyncpg.Record:
    su = await _superuser()
    try:
        row = await su.fetchrow("SELECT * FROM ledger.verify_chain($1)", w.tenant)
        assert row is not None
        return row
    finally:
        await su.close()


def D(x: str | int) -> Decimal:  # noqa: N802 - short constructor for readability
    return Decimal(x)


def sale(w: World, amount: str = "1500.00") -> list[Line]:
    return [(w.cash, D(amount), D(0)), (w.revenue, D(0), D(amount))]


# ============================================================================ L1 balance
async def test_balanced_draft_posts_and_chains(world: World) -> None:
    j = await draft(world, sale(world))
    seq = await post(world, j, await approve(world, j))
    assert seq == 1
    su = await _superuser()
    try:
        row = await su.fetchrow(
            "SELECT status, journal_no, period_id, approval_id IS NOT NULL AS approved "
            "FROM ledger.journals WHERE id = $1",
            j,
        )
        audited = await su.fetchval(
            "SELECT count(*) FROM audit.audit_events WHERE tenant_id = $1 "
            "AND action = 'ledger.journal.posted' AND resource_id = $2",
            world.tenant,
            str(j),
        )
    finally:
        await su.close()
    assert row is not None and dict(row) == {
        "status": "posted",
        "journal_no": 1,
        "period_id": world.period,
        "approved": True,
    }
    assert audited == 1
    assert dict(await verify(world)) == {"journals": 1, "ok": True, "first_bad_seq": None}


@pytest.mark.parametrize(
    "lines_fn",
    [
        lambda w: [(w.cash, D("100"), D(0)), (w.revenue, D(0), D("99.9999"))],  # off by 0.0001
        lambda w: [(w.cash, D("100"), D(0))],  # single line
        lambda w: [],  # no lines at all
    ],
    ids=["unbalanced", "single-line", "no-lines"],
)
async def test_unbalanced_or_incomplete_journals_never_commit(
    world: World, lines_fn: Callable[[World], list[Line]]
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await draft(world, lines_fn(world))
    su = await _superuser()
    try:
        assert (
            await su.fetchval(
                "SELECT count(*) FROM ledger.journals WHERE tenant_id = $1", world.tenant
            )
            == 0
        )
    finally:
        await su.close()


@pytest.mark.parametrize(
    ("debit", "credit"), [("10", "10"), ("-5", "0"), ("0", "0")], ids=["both", "negative", "zero"]
)
async def test_each_line_has_exactly_one_positive_side(
    world: World, debit: str, credit: str
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await draft(world, [(world.cash, D(debit), D(credit)), (world.revenue, D(0), D("10"))])


async def test_base_amounts_and_fx_rules(world: World) -> None:
    usd_line = {
        "account": world.expense,
        "debit": D("100"),
        "credit": D(0),
        "currency": "USD",
        "fx": D("281.2500"),
        "bd": D("28125.0000"),
        "bc": D(0),
    }
    bank = (world.cash, D(0), D("28125"))
    # A USD expense paid from PKR cash balances in base currency: accepted.
    await draft(world, [bank], extra=[usd_line])
    # A base amount that does not equal amount x rate: refused.
    with pytest.raises(asyncpg.CheckViolationError):
        await draft(world, [bank], extra=[{**usd_line, "bd": D("28000")}])
    # Functional-currency (PKR) lines must use rate 1.
    with pytest.raises(asyncpg.CheckViolationError):
        await draft(world, [bank], extra=[{**usd_line, "currency": "PKR"}])


# ============================================================================ L2 immutability
async def _posted(w: World) -> uuid.UUID:
    j = await draft(w, sale(w))
    await post(w, j, await approve(w, j))
    return j


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE ledger.journals SET description = 'edited' WHERE id = $1",
        "UPDATE ledger.journal_lines SET debit = 1 WHERE journal_id = $1",
        "DELETE FROM ledger.journal_lines WHERE journal_id = $1",
        "DELETE FROM ledger.journals WHERE id = $1",
    ],
)
async def test_ledger_role_cannot_edit_posted_entries(world: World, sql: str) -> None:
    j = await _posted(world)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await ledger_call(world, sql, j)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE ledger.journals SET description = 'edited' WHERE id = $1",
        "UPDATE ledger.journals SET status = 'draft' WHERE id = $1",
        "UPDATE ledger.journal_lines SET memo = 'x' WHERE journal_id = $1",
        "DELETE FROM ledger.journal_lines WHERE journal_id = $1",
        "DELETE FROM ledger.journals WHERE id = $1",
    ],
)
async def test_even_superuser_cannot_edit_posted_entries(world: World, sql: str) -> None:
    j = await _posted(world)
    su = await _superuser()
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await su.execute(sql, j)
    finally:
        await su.close()


async def test_lines_cannot_be_added_to_a_posted_journal(world: World) -> None:
    j = await _posted(world)
    conn = await _ledger()
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="draft journals"):
            async with conn.transaction():
                await _ctx(conn, world.tenant)
                for no, (acct, d, c) in enumerate(sale(world, "5"), start=10):
                    await conn.execute(
                        "INSERT INTO ledger.journal_lines (tenant_id, entity_id, journal_id, "
                        "line_no, account_id, debit, credit, currency, base_debit, base_credit, "
                        "evidence_type) VALUES ($1,$2,$3,$4,$5,$6,$7,'PKR',$6,$7,'system_calc')",
                        world.tenant,
                        world.entity,
                        j,
                        no,
                        acct,
                        d,
                        c,
                    )
    finally:
        await conn.close()


async def test_tampering_is_detected_by_the_chain(world: World) -> None:
    for _ in range(3):
        await _posted(world)
    su = await _superuser()
    try:
        tx = su.transaction()
        await tx.start()
        await su.execute(
            "ALTER TABLE ledger.journal_lines DISABLE TRIGGER trg_journal_lines_immutable"
        )
        # A balanced edit (both sides +1): every DB check still passes, only the chain catches it.
        await su.execute(
            "UPDATE ledger.journal_lines l SET debit = debit + 1, base_debit = base_debit + 1, "
            "credit = CASE WHEN credit > 0 THEN credit + 1 ELSE 0 END "
            "FROM ledger.journals j WHERE l.journal_id = j.id AND j.tenant_id = $1 "
            "AND j.ledger_seq = 2 AND l.debit > 0",
            world.tenant,
        )
        row = await su.fetchrow("SELECT * FROM ledger.verify_chain($1)", world.tenant)
        await tx.rollback()
    finally:
        await su.close()
    assert row is not None and row["ok"] is False and row["first_bad_seq"] == 2


# ============================================================================ L3 reversal
async def test_reversal_mirrors_lines_and_marks_original(world: World) -> None:
    original = await _posted(world)
    rev = await ledger_call(
        world,
        "SELECT ledger.create_reversal($1, '2026-04-01', 'Reverse wrong sale', $2)",
        original,
        world.reviewer,
    )
    await post(world, rev, await approve(world, rev))
    su = await _superuser()
    try:
        statuses: dict[uuid.UUID, str] = {
            r["id"]: r["status"]
            for r in await su.fetch(
                "SELECT id, status::text FROM ledger.journals WHERE id = ANY($1)", [original, rev]
            )
        }
        net = await su.fetch(
            "SELECT account_id, sum(base_debit - base_credit) AS net FROM ledger.journal_lines "
            "WHERE journal_id = ANY($1) GROUP BY account_id",
            [original, rev],
        )
    finally:
        await su.close()
    assert statuses == {original: "reversed", rev: "posted"}
    assert all(r["net"] == 0 for r in net)
    # A journal can be reversed once only.
    with pytest.raises(asyncpg.CheckViolationError, match="only posted"):
        await ledger_call(
            world,
            "SELECT ledger.create_reversal($1, '2026-04-02', 'again', $2)",
            original,
            world.reviewer,
        )
    assert (await verify(world))["ok"] is True


async def test_discarded_drafts_cannot_be_posted(world: World) -> None:
    j = await draft(world, sale(world))
    await ledger_call(world, "SELECT ledger.discard_journal($1, 'duplicate upload')", j)
    with pytest.raises(asyncpg.CheckViolationError, match="only drafts"):
        await post(world, j, await approve(world, j))


# ============================================================================ L5 periods
async def test_posting_needs_an_open_period(world: World) -> None:
    outside = await draft(world, sale(world), when=date(2027, 1, 5))
    with pytest.raises(asyncpg.CheckViolationError, match="no open period"):
        await post(world, outside, await approve(world, outside))

    inside = await draft(world, sale(world))
    await ledger_call(world, "SELECT ledger.lock_period($1)", world.period)
    with pytest.raises(asyncpg.CheckViolationError, match="no open period"):
        await post(world, inside, await approve(world, inside))

    # Reopening needs its own reviewer approval; then posting works again.
    reopen = await approve(world, world.period, kind="period_reopen")
    await ledger_call(world, "SELECT ledger.reopen_period($1, $2)", world.period, reopen)
    await post(world, inside, await approve(world, inside))


async def test_periods_never_overlap(world: World) -> None:
    conn = await _ledger()
    try:
        with pytest.raises(asyncpg.ExclusionViolationError):
            async with conn.transaction():
                await _ctx(conn, world.tenant)
                await conn.execute(
                    "INSERT INTO ledger.periods (tenant_id, entity_id, start_date, end_date) "
                    "VALUES ($1, $2, '2026-12-01', '2027-01-31')",
                    world.tenant,
                    world.entity,
                )
    finally:
        await conn.close()


# ============================================================================ L6 approvals
@pytest.mark.parametrize(
    "who", ["client", "reviewer_no_mfa", "agent"], ids=["client-owner", "no-mfa", "agent-user"]
)
async def test_only_mfa_reviewers_can_approve(world: World, who: str) -> None:
    j = await draft(world, sale(world))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await approve(world, j, by=getattr(world, who))


async def test_nobody_approves_in_someone_elses_name(world: World) -> None:
    j = await draft(world, sale(world))
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="current user"):
        await approve(world, j, by=world.client, claimed=world.reviewer)


async def test_approval_snapshot_cannot_be_forged(world: World) -> None:
    j = await draft(world, sale(world))
    a = await approve(world, j)  # the helper sends role 'client_owner' and name 'forged'
    su = await _superuser()
    try:
        row = await su.fetchrow(
            "SELECT approver_role::text, approver_name FROM app.approvals WHERE id = $1", a
        )
    finally:
        await su.close()
    assert row is not None and row["approver_role"] == "reviewer"
    assert row["approver_name"].startswith("reviewer ")


async def test_approval_must_match_and_is_single_use(world: World) -> None:
    j1, j2 = await draft(world, sale(world)), await draft(world, sale(world))
    a1 = await approve(world, j1)
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="does not authorise"):
        await post(world, j2, a1)  # approval was for j1
    await post(world, j1, a1)
    rev = await ledger_call(
        world, "SELECT ledger.create_reversal($1, '2026-04-01', 'r', $2)", j1, world.reviewer
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await post(world, rev, a1)  # already used, and for another subject


async def test_approvals_are_immutable(world: World) -> None:
    j = await draft(world, sale(world))
    a = await approve(world, j)
    su = await _superuser()
    try:
        for sql in (
            "UPDATE app.approvals SET comment = 'x' WHERE id = $1",
            "DELETE FROM app.approvals WHERE id = $1",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await su.execute(sql, a)
    finally:
        await su.close()


# ============================================================================ L8 tenancy
async def test_other_tenant_cannot_see_or_post(world: World) -> None:
    su = await _superuser()
    try:
        other = await _make_world(su)
    finally:
        await su.close()
    j = await draft(world, sale(world))
    a = await approve(world, j)
    conn = await _ledger()
    try:
        async with conn.transaction():
            await _ctx(conn, other.tenant, other.reviewer)
            assert await conn.fetchval("SELECT count(*) FROM ledger.journals") == 0
            assert await conn.fetchval("SELECT count(*) FROM ledger.journal_lines") == 0
        with pytest.raises(asyncpg.NoDataFoundError):
            async with conn.transaction():
                await _ctx(conn, other.tenant, other.reviewer)
                await conn.execute("SELECT ledger.post_journal($1, $2)", j, a)
        with pytest.raises(asyncpg.NoDataFoundError):
            async with conn.transaction():
                await _ctx(conn, other.tenant)
                await conn.execute("SELECT * FROM ledger.verify_chain($1)", world.tenant)
    finally:
        await conn.close()


async def test_lines_cannot_use_another_entitys_account(world: World) -> None:
    su = await _superuser()
    try:
        foreign = await su.fetchval(
            "INSERT INTO app.entities (tenant_id, legal_name, jurisdiction) "
            "VALUES ($1, 'Sister Co', 'PK') RETURNING id",
            world.tenant,
        )
        foreign_acct = await su.fetchval(
            "INSERT INTO ledger.accounts (tenant_id, entity_id, code, name, class) "
            "VALUES ($1, $2, '1000', 'Cash', 'asset') RETURNING id",
            world.tenant,
            foreign,
        )
    finally:
        await su.close()
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await draft(world, [(foreign_acct, D(10), D(0)), (world.revenue, D(0), D(10))])


# ============================================================================ properties
def _run[R](coro: Awaitable[R]) -> R:
    return asyncio.run(coro)  # type: ignore[arg-type]


amounts = st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("9999999.9999"), places=4)


@st.composite
def journal_amounts(draw: st.DrawFn) -> tuple[list[Decimal], list[Decimal]]:
    """Debits, and credits that split the same total - then, half the time, a small error."""
    debits = draw(st.lists(amounts, min_size=1, max_size=4))
    total = sum(debits, start=D(0))
    parts = draw(st.integers(min_value=1, max_value=3))
    credits: list[Decimal] = []
    remaining = total
    for _ in range(parts - 1):
        if remaining <= CENT:
            break
        share = draw(st.decimals(min_value=CENT, max_value=remaining - CENT, places=4))
        credits.append(share)
        remaining -= share
    credits.append(remaining)
    error = draw(st.sampled_from([D(0), D(0), D("0.0001"), D("-0.0001"), D("1"), D("-0.01")]))
    if credits[-1] + error > 0:
        credits[-1] += error
    return debits, credits


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(journal=journal_amounts())
def test_property_a_journal_persists_iff_it_balances(
    journal: tuple[list[Decimal], list[Decimal]],
) -> None:
    debits, credits = journal

    async def scenario() -> tuple[bool, bool]:
        su = await _superuser()
        try:
            w = await _make_world(su)
        finally:
            await su.close()
        lines: list[Line] = [(w.cash, d, D(0)) for d in debits] + [
            (w.revenue, D(0), c) for c in credits
        ]
        balanced = sum(debits) == sum(credits)
        try:
            await draft(w, lines)
            persisted = True
        except asyncpg.CheckViolationError:
            persisted = False
        return balanced, persisted

    balanced, persisted = _run(scenario())
    event(f"balanced={balanced}")  # both outcomes must show up in --hypothesis-show-statistics
    assert persisted == balanced


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    amount=amounts,
    rate=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("999.9999"), places=4),
)
def test_property_foreign_line_base_is_rounded_amount_times_rate(
    amount: Decimal, rate: Decimal
) -> None:
    base = (amount * rate).quantize(CENT, rounding=ROUND_HALF_UP)  # what calculators produce
    if base == 0 or base >= Decimal("1e16"):
        return

    async def scenario() -> None:
        su = await _superuser()
        try:
            w = await _make_world(su)
        finally:
            await su.close()
        await draft(
            w,
            [(w.cash, D(0), base)],
            extra=[
                {
                    "account": w.expense,
                    "debit": amount,
                    "credit": D(0),
                    "currency": "USD",
                    "fx": rate,
                    "bd": base,
                    "bc": D(0),
                }
            ],
        )

    _run(scenario())


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    column=st.sampled_from(["debit", "credit", "memo", "account_id", "line_no"]),
    action=st.sampled_from(["update", "delete"]),
)
def test_property_no_edit_of_a_posted_journal_persists(column: str, action: str) -> None:
    async def scenario() -> tuple[bool, asyncpg.Record]:
        su = await _superuser()
        try:
            w = await _make_world(su)
        finally:
            await su.close()
        j = await draft(w, sale(w))
        await post(w, j, await approve(w, j))
        value = {
            "debit": "debit",
            "credit": "credit",
            "memo": "'edited'",
            "account_id": "account_id",
            "line_no": "line_no + 10",
        }[column]
        sql = (
            f"UPDATE ledger.journal_lines SET {column} = {value} WHERE journal_id = $1"  # noqa: S608
            if action == "update"
            else "DELETE FROM ledger.journal_lines WHERE journal_id = $1"
        )
        refused = False
        try:
            await ledger_call(w, sql, j)
        except asyncpg.InsufficientPrivilegeError:
            refused = True
        return refused, await verify(w)

    refused, chain = _run(scenario())
    assert refused and chain["ok"] is True
