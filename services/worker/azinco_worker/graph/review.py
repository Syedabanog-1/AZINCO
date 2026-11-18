"""Two-node review graph (Step 0.10b skeleton, ADR-0002): AI proposes -> human decides.

    START -> prepare -> human_review (interrupt) -> END

* `prepare` asks the Model Gateway for a categorisation *proposal* (no amounts).
* `human_review` pauses the graph with `interrupt()`. In the first release EVERY item goes to the
  Reviewer, whatever the confidence (BS §8.8). The run resumes only with a validated
  `ReviewDecision`; the graph itself can never approve.
* With a checkpointer every step is persisted, so a crash after `prepare` resumes at
  `human_review` without calling the model again.

The public API (Phase 1) is responsible for checking that the decision comes from an
authenticated, MFA-verified reviewer before it calls `resume()`; the ledger still demands its own
approval row before anything is posted (ADR-0015).
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, ConfigDict, Field

from azinco_worker.gateway import ModelGateway, ModelRequest

CATEGORIZE_TASK = "categorize.document"
# Bump CATEGORIZE_PROMPT_VERSION whenever the instructions change: golden-set reports record it.
CATEGORIZE_PROMPT_VERSION = "categorize-v1"
CATEGORIZE_INSTRUCTIONS = (
    "Propose the expense account for this document. "
    "Return only a label, an account code from the client's chart and a confidence."
)


class CategoryProposal(BaseModel):
    """What the model may return: a label and a score - never a figure."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    account_code: str = Field(pattern=r"^[0-9A-Za-z][0-9A-Za-z.\-]{0,19}$")
    label: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list, max_length=5)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reviewer_id: uuid.UUID
    decision: Literal["approve", "reject", "rework"]
    account_code: str | None = Field(default=None, pattern=r"^[0-9A-Za-z][0-9A-Za-z.\-]{0,19}$")
    comment: str | None = Field(default=None, max_length=1000)


class ReviewState(TypedDict, total=False):
    tenant_id: str
    task_id: str
    document_text: str
    proposal: dict[str, Any]
    model_call_ids: list[str]
    decision: dict[str, Any]
    status: Literal["awaiting_review", "approved", "rejected", "rework"]


def categorize_request(document_text: str) -> ModelRequest:
    """The categorisation request used by the graph AND by golden-set runs (same path measured)."""
    return ModelRequest(
        agent="categorization",
        task=CATEGORIZE_TASK,
        instructions=CATEGORIZE_INSTRUCTIONS,
        untrusted_document=document_text,
    )


def thread_id(tenant_id: uuid.UUID, task_id: uuid.UUID) -> str:
    """Checkpoint thread ids are tenant-prefixed so state can never be mixed across tenants."""
    return f"{tenant_id}:{task_id}"


def build_review_graph(
    gateway: ModelGateway, checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledStateGraph[Any, Any, Any, Any]:
    def prepare(state: ReviewState) -> ReviewState:
        result = gateway.complete(categorize_request(state["document_text"]), CategoryProposal)
        return {
            "proposal": result.output.model_dump(),
            "model_call_ids": [result.record.call_id],
            "status": "awaiting_review",
        }

    def human_review(state: ReviewState) -> ReviewState:
        raw = interrupt(
            {"kind": "review_required", "task_id": state["task_id"], "proposal": state["proposal"]}
        )
        decision = ReviewDecision.model_validate(raw)
        status: Literal["approved", "rejected", "rework"] = {
            "approve": "approved",
            "reject": "rejected",
            "rework": "rework",
        }[decision.decision]  # type: ignore[assignment]
        return {"decision": decision.model_dump(mode="json"), "status": status}

    graph = StateGraph(ReviewState)
    graph.add_node("prepare", prepare)
    graph.add_node("human_review", human_review)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "human_review")
    graph.add_edge("human_review", END)
    return graph.compile(checkpointer=checkpointer)


def _config(tenant_id: uuid.UUID, task_id: uuid.UUID) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id(tenant_id, task_id)}}


def start(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    document_text: str,
) -> dict[str, Any]:
    state: ReviewState = {
        "tenant_id": str(tenant_id),
        "task_id": str(task_id),
        "document_text": document_text,
    }
    result: dict[str, Any] = graph.invoke(state, _config(tenant_id, task_id))
    return result


def resume(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    decision: ReviewDecision,
) -> dict[str, Any]:
    command: Command[Any] = Command(resume=decision.model_dump(mode="json"))
    result: dict[str, Any] = graph.invoke(command, _config(tenant_id, task_id))
    return result
