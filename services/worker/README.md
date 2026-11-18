# services/worker — Model Gateway + LangGraph graphs

Background workers for the agent pipeline (Base Standard §7, §8). **No agent writes the posted
ledger**: agents propose, deterministic services calculate, humans approve.

## Model Gateway (`azinco_worker.gateway`, ADR-0004)

Agents call `ModelGateway.complete(ModelRequest, OutputModel)`, never a provider SDK.

* Routes each agent to a provider/model by configuration (`routes`), so OpenAI / Anthropic /
  Gemini can be swapped and compared. Phase 0 ships only the **[MOCK]** provider (deterministic,
  offline). Real providers are added in Phase 1 behind the same `Provider` protocol.
* Document text is **data**: masked (emails, 9+ digit numbers such as CNIC/IBAN/card/account) and
  fenced in `<untrusted_document>`; a document cannot close the fence (prompt-injection defence).
* Output must validate against the caller's Pydantic model (extra fields rejected — a model cannot
  smuggle figures in); one retry, then `OutputValidationError`.
* Per-run call/token **budget**; every call produces a `CallRecord` (agent, task, provider, model,
  tokens, latency, attempts, outcome, masked count — no prompt text) for audit.

## Review graph (`azinco_worker.graph`, ADR-0002)

`START → prepare → human_review (interrupt) → END`. `prepare` gets a categorisation **proposal**;
`human_review` pauses with `interrupt()` for **every** item (§8.8) and resumes only with a validated
`ReviewDecision`. Checkpoints go to PostgreSQL schema `agent_state` (migration 0006) as role
`azinco_worker`, which cannot write `app`, `ledger` or `audit`. Thread ids are tenant-prefixed.

Proven by tests: a child process reaches the interrupt and is killed with `os._exit(1)`; a fresh
process resumes from PostgreSQL and finishes **without calling the model again**.

## Tests

`docker compose ... --profile test run --rm worker-test` → `WORKER-TESTS-OK`.
