# ADR-0004: Model Gateway — one model-agnostic door for every agent

| Field | Value |
|---|---|
| Status | Accepted (implemented in Step 0.10b with the [MOCK] provider) |
| Date | 2026-11-18 |
| Deciders | Engineer |
| Requirements | FR-AGT-06, NFR-SEC (masking, prompt injection), KPI AI cost |
| Base Standard | §7.8 (AI cost and quality KPIs), §8.1 (models judge, code calculates), §8.6 (model registry), §12 (masking in prompts, prompt-injection defences) |
| Label | [Source] requirements, [Recommended] design |

## Context
Project rule: the platform must swap and compare models (OpenAI, Claude, Gemini, …) from day one,
LLMs never produce authoritative figures, document text is data not instructions, and sensitive
data is masked where possible.

## Decision
`azinco_worker.gateway.ModelGateway.complete(ModelRequest, OutputModel)`:
* **Routing by configuration**: agent → `Route(provider, model)` with a `default`; providers
  implement one `Provider` protocol. Phase 0: only `MockProvider` ([MOCK], deterministic, offline).
* **Untrusted data fence**: document text is placed after the instructions inside
  `<untrusted_document>…</untrusted_document>`; any fence tag inside the document is removed, so
  the document cannot end the fence (property-tested). The system prompt says fenced text is data.
* **Masking** before sending: emails and 9+ digit runs (CNIC, IBAN parts, card and account
  numbers) become placeholders; amounts and short numbers are kept.
* **Typed output**: JSON validated against the caller's Pydantic model with `extra="forbid"`;
  one retry, then `OutputValidationError`. No figure from a model is ever used as a figure.
* **Budget** per run (calls, tokens) [Recommended]; `AZINCO_MODEL_DAILY_BUDGET_USD` applies when
  real providers are added.
* **Call records** for audit and the model registry: agent, task, provider, model, tokens,
  latency, attempts, outcome, masked count — never the prompt text or secrets.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. Own thin gateway + provider protocol (chosen) | Our controls in one place; easy to test; no vendor lock-in | We maintain adapters |
| B. Third-party router (e.g. LiteLLM) behind our gateway | Many providers quickly | Extra dependency; still need our fence/masking/validation — can be added as one `Provider` later |
| C. Call vendor SDKs from agents | Fastest to start | Controls scattered; impossible to compare models fairly |

## Consequences
* Real providers (OpenAI, Anthropic, Gemini) arrive in Phase 1 as `Provider` implementations, with
  keys only from `.env`/secret store, sandbox budgets, and the golden-set comparison (§8.8).
* Masking is pattern-based and conservative; it reduces but does not eliminate exposure, so the
  data-processing terms of each provider are part of provider onboarding (GAP for legal review).
