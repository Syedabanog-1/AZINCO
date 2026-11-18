"""Ledger Service end to end against PostgreSQL (migration 0005 applied). Synthetic data only.

World setup (tenant, users, entity) uses the bootstrap superuser - a test fixture only. The service
itself connects as `azinco_ledger`; approvals are inserted as `azinco_app` signed in as the
reviewer, exactly as the public API will do in Phase 1.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from azinco_ledger.api import create_app
from azinco_ledger.config import LedgerSettings
from azinco_ledger.domain import base_amount

API_TOKEN = "test-api-token-" + "a" * 32  # [MOCK] test-only service tokens
WORKER_TOKEN = "test-worker-token-" + "b" * 32

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.environ.get("AZINCO_INTEGRATION_DB") and os.environ.get("POSTGRES_SUPERUSER")),
        reason="needs PostgreSQL (AZINCO_INTEGRATION_DB=1 and POSTGRES_SUPERUSER)",
    ),
]


def _dsn(user: str, password: str) -> dict[str, Any]:
    return {
        "host": os.environ.get("POSTGRES_HOST", "postgres"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "database": os.environ.get("POSTGRES_DB", "azinco"),
        "user": user,
        "password": password,
    }


async def _superuser() -> asyncpg.Connection:
    return await asyncpg.connect(
        **_dsn(
            os.environ["POSTGRES_SUPERUSER"],
            os.environ.get("POSTGRES_SUPERUSER_PASSWORD", "unused"),
        )
    )


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    entity: uuid.UUID
    reviewer: uuid.UUID
    agent: uuid.UUID


async def _make_world() -> World:
    su = await _superuser()
    try:
        t, e, reviewer, agent = (uuid.uuid4() for _ in range(4))
        tag = t.hex[:8]
        await su.execute(
            "INSERT INTO app.tenants (id, name, home_jurisdiction) "
            "VALUES ($1, 'Synthetic Ledger Co', 'PK')",
            t,
        )
        for uid, kind, utype in ((reviewer, "reviewer", "staff"), (agent, "agent", "system")):
            await su.execute(
                "INSERT INTO app.users (id, email, display_name, user_type, status, mfa_enabled) "
                "VALUES ($1, $2, $3, $4, 'active', true)",
                uid,
                f"{kind}-{tag}@example.com",
                f"{kind} {tag}",
                utype,
            )
        await su.execute(
            "INSERT INTO app.tenant_memberships (tenant_id, user_id, role) "
            "VALUES ($1, $2, 'reviewer')",
            t,
            reviewer,
        )
        await su.execute(
            "INSERT INTO app.entities (id, tenant_id, legal_name, jurisdiction) "
            "VALUES ($1, $2, 'Synthetic Traders (Pvt) Ltd', 'PK')",
            e,
            t,
        )
        return World(t, e, reviewer, agent)
    finally:
        await su.close()


def approve(w: World, subject: uuid.UUID, kind: str = "journal_post") -> str:
    """The reviewer's click, as the public API (azinco_app) will record it."""

    async def run() -> str:
        conn = await asyncpg.connect(**_dsn("azinco_app", os.environ["AZINCO_DB_APP_PASSWORD"]))
        try:
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.tenant_id', $1, true), "
                    "set_config('app.user_id', $2, true)",
                    str(w.tenant),
                    str(w.reviewer),
                )
                return str(
                    await conn.fetchval(
                        "INSERT INTO app.approvals (tenant_id, subject_type, subject_id, "
                        "approver_id, approver_role, approver_name) "
                        "VALUES ($1, $2, $3, $4, 'reviewer', '-') "
                        "RETURNING id",
                        w.tenant,
                        kind,
                        subject,
                        w.reviewer,
                    )
                )
        finally:
            await conn.close()

    return asyncio.run(run())


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    cfg = LedgerSettings.model_validate(
        {
            "AZINCO_ENV": "ci",
            "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "postgres"),
            "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "POSTGRES_DB": os.environ.get("POSTGRES_DB", "azinco"),
            "AZINCO_DB_LEDGER_PASSWORD": SecretStr(os.environ["AZINCO_DB_LEDGER_PASSWORD"]),
            "AZINCO_LEDGER_API_TOKEN": SecretStr(API_TOKEN),
            "AZINCO_LEDGER_WORKER_TOKEN": SecretStr(WORKER_TOKEN),
        }
    )
    with TestClient(create_app(cfg)) as c:
        yield c


class Ledger:
    """Small client: one tenant/actor, API or worker token."""

    def __init__(
        self, c: TestClient, w: World, *, worker: bool = False, tenant: uuid.UUID | None = None
    ) -> None:
        self.c, self.w = c, w
        self.headers = {
            "Authorization": f"Bearer {WORKER_TOKEN if worker else API_TOKEN}",
            "X-Tenant-Id": str(tenant or w.tenant),
            "X-Actor-Id": str(w.agent if worker else w.reviewer),
        }

    def post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.c.post(f"/internal/ledger{path}", json=body or {}, headers=self.headers)

    def get(self, path: str) -> Any:
        return self.c.get(f"/internal/ledger{path}", headers=self.headers)


@pytest.fixture
def books(client: TestClient) -> tuple[Ledger, dict[str, str]]:
    w = asyncio.run(_make_world())
    led = Ledger(client, w)
    accounts = {}
    for code, name, cls in (
        ("1000", "Cash", "asset"),
        ("4000", "Sales", "revenue"),
        ("6000", "Rent", "opex"),
    ):
        r = led.post(
            "/accounts",
            {"entity_id": str(w.entity), "code": code, "name": name, "account_class": cls},
        )
        assert r.status_code == 201, r.text
        accounts[code] = r.json()["id"]
    r = led.post(
        "/periods",
        {"entity_id": str(w.entity), "start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert r.status_code == 201, r.text
    accounts["period"] = r.json()["id"]
    return led, accounts


def sale(led: Ledger, a: dict[str, str], amount: str = "1500.50", **extra: Any) -> dict[str, Any]:
    return {
        "entity_id": str(led.w.entity),
        "journal_date": "2026-03-31",
        "description": "Synthetic sale",
        "source": "agent",
        "lines": [
            {
                "account_id": a["1000"],
                "debit": amount,
                "currency": "PKR",
                "evidence_type": "system_calc",
            },
            {
                "account_id": a["4000"],
                "credit": amount,
                "currency": "PKR",
                "evidence_type": "system_calc",
            },
        ],
        **extra,
    }


# ------------------------------------------------------------------ auth & scopes
def test_service_token_is_required(client: TestClient) -> None:
    hdr = {"X-Tenant-Id": str(uuid.uuid4()), "X-Actor-Id": str(uuid.uuid4())}
    assert client.get("/internal/ledger/verify", headers=hdr).status_code == 401
    bad = {**hdr, "Authorization": "Bearer " + "x" * 40}
    r = client.get("/internal/ledger/verify", headers=bad)
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated"
    assert r.headers["content-type"].startswith("application/problem+json")


def test_workers_draft_but_never_post(books: tuple[Ledger, dict[str, str]]) -> None:
    led, a = books
    agent = Ledger(led.c, led.w, worker=True)
    r = agent.post("/drafts", sale(led, a))
    assert r.status_code == 201, r.text
    j = r.json()["id"]
    for path, body in (
        ("/post", {"journal_id": j, "approval_id": approve(led.w, j)}),
        ("/reverse", {"journal_id": j, "reversal_date": "2026-04-01", "description": "x"}),
        (f"/periods/{a['period']}/lock", {}),
    ):
        r = agent.post(path, body)
        assert r.status_code == 403 and r.json()["code"] == "scope_denied", path


# ------------------------------------------------------------------ happy path
def test_draft_post_reverse_and_verify(books: tuple[Ledger, dict[str, str]]) -> None:
    led, a = books
    r = led.post("/drafts", sale(led, a))
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["status"] == "draft"
    assert [(ln["base_debit"], ln["base_credit"]) for ln in draft["lines"]] == [
        ("1500.5000", "0.0000"),
        ("0.0000", "1500.5000"),
    ]

    r = led.post("/post", {"journal_id": draft["id"], "approval_id": approve(led.w, draft["id"])})
    assert r.status_code == 200, r.text
    posted = r.json()
    assert (posted["status"], posted["journal_no"], posted["ledger_seq"]) == ("posted", 1, 1)
    assert len(posted["row_hash"]) == 64

    r = led.post(
        "/reverse",
        {
            "journal_id": draft["id"],
            "reversal_date": "2026-04-01",
            "description": "Reverse wrong sale",
        },
    )
    assert r.status_code == 201, r.text
    rev = r.json()
    assert [(ln["debit"], ln["credit"]) for ln in rev["lines"]] == [
        ("0.0000", "1500.5000"),
        ("1500.5000", "0.0000"),
    ]
    assert (
        led.post(
            "/post", {"journal_id": rev["id"], "approval_id": approve(led.w, rev["id"])}
        ).status_code
        == 200
    )
    assert led.get(f"/journals/{draft['id']}").json()["status"] == "reversed"
    assert led.get("/verify").json() == {"journals": 2, "ok": True, "first_bad_seq": None}


def test_foreign_currency_base_is_computed_by_the_service(
    books: tuple[Ledger, dict[str, str]],
) -> None:
    led, a = books
    body = sale(led, a)
    body["lines"] = [
        {
            "account_id": a["6000"],
            "debit": "100",
            "currency": "USD",
            "fx_rate": "281.255",
            "evidence_type": "system_calc",
        },
        {
            "account_id": a["1000"],
            "credit": "28125.5",
            "currency": "PKR",
            "evidence_type": "system_calc",
        },
    ]
    r = led.post("/drafts", body)
    assert r.status_code == 201, r.text
    assert r.json()["lines"][0]["base_debit"] == "28125.5000"


# ------------------------------------------------------------------ rules surface as problems
@pytest.mark.parametrize(
    ("mutate", "status", "code"),
    [
        (lambda b: b["lines"][1].update(credit="1500.49"), 422, "unbalanced"),
        (lambda b: b["lines"][0].update(base_debit="1"), 422, "invalid_request"),
        (lambda b: b["lines"][0].update(debit=1500.5), 422, "invalid_request"),  # JSON float
        (lambda b: b.update(entity_id=str(uuid.uuid4())), 404, "not_found"),
        (lambda b: b["lines"][0].update(account_id=str(uuid.uuid4())), 422, "unknown_reference"),
        (lambda b: b.update(journal_date="2027-02-01"), 201, None),  # drafts allowed; posting not
    ],
    ids=["unbalanced", "caller-base", "float", "unknown-entity", "unknown-account", "no-period"],
)
def test_draft_rules(
    books: tuple[Ledger, dict[str, str]], mutate: Any, status: int, code: str | None
) -> None:
    led, a = books
    body = sale(led, a)
    mutate(body)
    r = led.post("/drafts", body)
    assert r.status_code == status, r.text
    if code:
        assert r.json()["code"] == code


def test_posting_rules(books: tuple[Ledger, dict[str, str]]) -> None:
    led, a = books
    j1 = led.post("/drafts", sale(led, a)).json()["id"]
    j2 = led.post("/drafts", sale(led, a)).json()["id"]
    # No approval / approval for another journal.
    r = led.post("/post", {"journal_id": j1, "approval_id": str(uuid.uuid4())})
    assert (r.status_code, r.json()["code"]) == (403, "not_authorised")
    r = led.post("/post", {"journal_id": j2, "approval_id": approve(led.w, j1)})
    assert (r.status_code, r.json()["code"]) == (403, "not_authorised")
    # Locked period.
    assert led.post(f"/periods/{a['period']}/lock").status_code == 204
    r = led.post("/post", {"journal_id": j1, "approval_id": approve(led.w, j1)})
    assert (r.status_code, r.json()["code"]) == (422, "ledger_rule")
    assert "no open period" in r.json()["detail"]
    # Reopen needs a reviewer approval for the period.
    r = led.post(
        f"/periods/{a['period']}/reopen",
        {"approval_id": approve(led.w, uuid.UUID(a["period"]), "period_reopen")},
    )
    assert r.status_code == 204, r.text
    assert (
        led.post("/post", {"journal_id": j2, "approval_id": approve(led.w, j2)}).status_code == 200
    )
    # Overlapping period.
    r = led.post(
        "/periods",
        {"entity_id": str(led.w.entity), "start_date": "2026-06-01", "end_date": "2027-05-31"},
    )
    assert (r.status_code, r.json()["code"]) == (409, "period_overlap")


def test_discard_and_tenant_isolation(books: tuple[Ledger, dict[str, str]]) -> None:
    led, a = books
    j = led.post("/drafts", sale(led, a)).json()["id"]
    stranger = Ledger(led.c, asyncio.run(_make_world()))
    assert stranger.get(f"/journals/{j}").status_code == 404
    assert stranger.post("/discard", {"journal_id": j, "reason": "x"}).status_code == 404
    r = led.post("/discard", {"journal_id": j, "reason": "duplicate upload"})
    assert r.status_code == 200 and r.json()["status"] == "discarded"


def test_actions_are_audited(books: tuple[Ledger, dict[str, str]]) -> None:
    led, a = books
    j = led.post("/drafts", sale(led, a)).json()["id"]
    led.post("/post", {"journal_id": j, "approval_id": approve(led.w, j)})

    async def actions() -> list[str]:
        su = await _superuser()
        try:
            rows = await su.fetch(
                "SELECT action FROM audit.audit_events WHERE tenant_id = $1 ORDER BY seq",
                led.w.tenant,
            )
        finally:
            await su.close()
        return [r["action"] for r in rows]

    assert asyncio.run(actions()) == [
        "ledger.account.created",
        "ledger.account.created",
        "ledger.account.created",
        "ledger.period.created",
        "ledger.journal.drafted",
        "ledger.journal.posted",
    ]


def test_probes(client: TestClient) -> None:
    assert client.get("/health").json()["service"] == "azinco-ledger"
    assert client.get("/ready").json() == {"status": "ready"}


# ------------------------------------------------------------------ code == database
@settings(max_examples=40, deadline=None)
@given(
    amount=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("99999999.9999"), places=4),
    rate=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("9999.9999999999"), places=10),
)
def test_property_code_and_database_round_identically(amount: Decimal, rate: Decimal) -> None:
    async def db_round() -> Decimal:
        su = await _superuser()
        try:
            return Decimal(
                await su.fetchval(
                    "SELECT round($1::numeric(20,4) * $2::numeric(20,10), 4)", amount, rate
                )
            )
        finally:
            await su.close()

    assert base_amount(amount, rate) == asyncio.run(db_round())
