# ADR-0002: Orchestration — LangGraph with a PostgreSQL checkpointer and human interrupts

| Field | Value |
|---|---|
| Status | Accepted (skeleton implemented in Step 0.10b) |
| Date | 2026-11-18 |
| Deciders | Engineer |
| Requirements | FR-AGT-01..06, HITL-01..02 |
| Base Standard | §7.1 (supervisor + state graph with retries, checkpoints, human interrupts), §7.5, §8.8 (first release: every item to the Reviewer), §11.2 (OpenAI Agents SDK and/or LangGraph) |
| Label | [Source] requirements, [Recommended] library and storage choices |

## Context
The 15-component agent system needs an explicit state graph that survives crashes and pauses for
human decisions for as long as a reviewer needs (hours or days) without holding a process.

## Decision
* **LangGraph** (1.x) for graphs; `interrupt()` + `Command(resume=…)` for human-in-the-loop.
* **`langgraph-checkpoint-postgres`** stores every step in PostgreSQL schema `agent_state`
  (migration 0006). Role `azinco_worker` has USAGE + CREATE there and no write access to `app`,
  `ledger` or `audit` (checked by `verify_stack.py`).
* Thread ids are `"{tenant_id}:{task_id}"` [Recommended]. Graph state carries ids, proposals and
  decisions — not credentials, and not posted figures.
* First graph (`azinco_worker.graph.review`): `prepare` (Model Gateway proposal) →
  `human_review` (interrupt for **every** item, §8.8) → END. Resume input is a validated
  `ReviewDecision`; the graph cannot approve on its own.
* Exit criterion met by test: a child process reaches the interrupt and dies with `os._exit(1)`;
  a fresh process resumes from PostgreSQL and completes without calling the model again.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. LangGraph + Postgres checkpointer (chosen) | Durable interrupts; explicit graph; same DB, backups, no new infra | Library-managed tables (cannot carry our RLS) |
| B. OpenAI Agents SDK only | Simple tool calling | Durable long human pauses need extra infrastructure; tied to one vendor's runtime |
| C. Temporal / custom state machine | Very strong durability | New cluster to run; more code before value |

## Consequences
* Checkpoint tables are created by the library (`setup()`, idempotent) and owned by
  `azinco_worker`; they have no RLS. Mitigations: tenant-prefixed thread ids, the worker role is the
  only reader/writer, state holds references not documents. [Recommended, Phase 1] encrypt
  sensitive state fields and add a retention job.
* The OpenAI Agents SDK may still be used **inside** a node for tool calling; orchestration,
  checkpoints and interrupts stay in LangGraph.
* The public API (Phase 1) must check that a resume comes from an authenticated MFA reviewer; the
  ledger independently requires its own approval row (ADR-0015).
