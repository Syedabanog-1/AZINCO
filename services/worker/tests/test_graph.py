"""Review graph: interrupt -> resume, every item reviewed, and resume after a real process crash.

Roadmap Step 0.10 exit criterion: "graph resumes after simulated crash". The crash test runs the
first half in a separate Python process that dies with os._exit(1) right after the interrupt is
checkpointed (no cleanup, no graceful shutdown); a fresh process then resumes from PostgreSQL.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import uuid

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from azinco_worker.graph import ReviewDecision, build_review_graph, resume, start, thread_id
from azinco_worker.graph.demo import mock_gateway

TENANT = uuid.UUID("00000000-0000-4000-8000-0000000000aa")
DOC = "[MOCK] Invoice from Synthetic Landlord Ltd - office rent March 2026."

needs_pg = pytest.mark.skipif(
    not (os.environ.get("AZINCO_INTEGRATION_DB") and os.environ.get("AZINCO_DB_WORKER_PASSWORD")),
    reason="needs PostgreSQL (AZINCO_INTEGRATION_DB=1 and AZINCO_DB_WORKER_PASSWORD)",
)


def decision(kind: str = "approve") -> ReviewDecision:
    return ReviewDecision.model_validate({"reviewer_id": str(uuid.uuid4()), "decision": kind})


def test_every_item_stops_for_human_review() -> None:
    gw, provider = mock_gateway()
    graph = build_review_graph(gw, InMemorySaver())
    task = uuid.uuid4()
    out = start(graph, tenant_id=TENANT, task_id=task, document_text=DOC)
    assert out["status"] == "awaiting_review"
    pending = out["__interrupt__"][0].value
    assert pending["kind"] == "review_required" and pending["proposal"]["account_code"] == "6000"
    assert "decision" not in out  # nothing decided without a human
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("kind", "status"), [("approve", "approved"), ("reject", "rejected"), ("rework", "rework")]
)
def test_resume_applies_the_reviewers_decision(kind: str, status: str) -> None:
    gw, provider = mock_gateway()
    graph = build_review_graph(gw, InMemorySaver())
    task = uuid.uuid4()
    start(graph, tenant_id=TENANT, task_id=task, document_text=DOC)
    d = decision(kind)
    out = resume(graph, tenant_id=TENANT, task_id=task, decision=d)
    assert out["status"] == status and out["decision"]["reviewer_id"] == str(d.reviewer_id)
    assert len(provider.calls) == 1  # resuming never re-asks the model


def test_a_resume_without_a_valid_decision_is_refused() -> None:
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate({"decision": "approve"})  # no reviewer
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate({"reviewer_id": str(uuid.uuid4()), "decision": "auto"})


def test_thread_ids_are_tenant_scoped() -> None:
    task = uuid.uuid4()
    assert thread_id(TENANT, task) != thread_id(uuid.uuid4(), task)
    assert thread_id(TENANT, task).startswith(str(TENANT))


_CRASHING_CHILD = textwrap.dedent(
    """
    import os, sys, uuid
    from azinco_worker.graph import build_review_graph, start
    from azinco_worker.graph.checkpoint import postgres_checkpointer
    from azinco_worker.graph.demo import mock_gateway

    tenant, task = uuid.UUID(sys.argv[1]), uuid.UUID(sys.argv[2])
    gateway, provider = mock_gateway()
    with postgres_checkpointer() as saver:
        out = start(build_review_graph(gateway, saver), tenant_id=tenant, task_id=task,
                    document_text=sys.argv[3])
        assert out["status"] == "awaiting_review" and len(provider.calls) == 1
        print("CHILD-REACHED-INTERRUPT", flush=True)
        os._exit(1)  # simulated crash: no cleanup, no graceful shutdown
    """
)


@pytest.mark.integration
@needs_pg
def test_graph_resumes_after_a_real_process_crash() -> None:
    from azinco_worker.graph.checkpoint import postgres_checkpointer

    task = uuid.uuid4()
    child = subprocess.run(
        [sys.executable, "-c", _CRASHING_CHILD, str(TENANT), str(task), DOC],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert child.returncode == 1, child.stderr
    assert "CHILD-REACHED-INTERRUPT" in child.stdout

    gateway, provider = mock_gateway()  # a brand-new process state: nothing in memory
    with postgres_checkpointer() as saver:
        graph = build_review_graph(gateway, saver)
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id(TENANT, task)}})
        assert snapshot.next == ("human_review",)
        assert snapshot.values["proposal"]["account_code"] == "6000"
        d = decision("approve")
        out = resume(graph, tenant_id=TENANT, task_id=task, decision=d)
    assert out["status"] == "approved"
    assert out["decision"]["reviewer_id"] == str(d.reviewer_id)
    assert provider.calls == []  # the model was not called again after the crash


@pytest.mark.integration
@needs_pg
def test_worker_role_cannot_touch_the_books() -> None:
    import psycopg

    from azinco_worker.graph.checkpoint import worker_conninfo

    with psycopg.connect(worker_conninfo(), autocommit=True) as conn:
        for sql in (
            "INSERT INTO ledger.journals (tenant_id, entity_id, journal_date, description, "
            "source) VALUES (gen_random_uuid(), gen_random_uuid(), current_date, 'x', 'agent')",
            "SELECT ledger.post_journal(gen_random_uuid(), gen_random_uuid())",
            "CREATE TABLE public.sneaky (id int)",
            "INSERT INTO app.approvals (tenant_id, subject_type, subject_id, approver_id, "
            "approver_role, approver_name) VALUES (gen_random_uuid(), 'journal_post', "
            "gen_random_uuid(), gen_random_uuid(), 'reviewer', 'agent')",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)
