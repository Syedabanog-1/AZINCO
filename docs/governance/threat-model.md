# AZINCO threat model — Phase 0 (STRIDE)

| Field | Value |
|---|---|
| Scope | Phase 0 stack: web (Next.js), API (FastAPI), Ledger Service, worker (Model Gateway + LangGraph), PostgreSQL, Redis, object storage, ClamAV, Mailpit (dev), CI |
| Method | STRIDE per trust boundary; controls must have **evidence** (a test or a `verify_stack` check) |
| Base Standard | §12 (security and data protection), §8.4 (ledger controls), §8.7 (approvals), §7 (agents) |
| Status | Draft for Phase 0 security review — reviewed by: _pending_ |
| Out of scope (Phase 1+) | Payments and webhooks (ADR-0011), OCR, real LLM providers, production hosting (ADR-0013) |

Legend: ✅ control in place with evidence · 🟡 partial · ⏳ planned (phase) · Residual risk: L/M/H.

## Assets

Client financial documents and extracted data; posted ledger and audit trail (integrity is the
product); reviewer approvals (legal significance, §8.7); credentials (sessions, MFA secrets, service
tokens, DB passwords); tenant boundaries; model prompts/outputs; rule-pack content.

## Trust boundaries

1. Browser ↔ web (same-origin proxy to the API)
2. Web/API ↔ PostgreSQL (role per service, RLS)
3. API ↔ Ledger Service (internal network, service tokens)
4. Worker ↔ Model Gateway ↔ LLM provider (untrusted output; external party in Phase 1)
5. Client document → ingestion → model prompt (untrusted input)
6. CI ↔ GitHub ↔ third-party actions and images (supply chain)

## STRIDE

| # | Threat | Boundary | Controls | Evidence | Residual |
|---|---|---|---|---|---|
| S1 | Stolen password used to sign in | 1 | Argon2id; lockout after 5 failures/15 min; TOTP MFA required for staff, reviewer, platform roles; email verification | `test_auth_flow.py`, ADR-0006 | M (MFA optional for clients) |
| S2 | Session hijack / CSRF | 1 | HttpOnly SameSite=Strict cookie; hashed session token; CSRF double-submit header | `test_auth_flow.py` | L |
| S3 | A caller impersonates the API to the ledger | 3 | Bearer service tokens (≥32 chars, constant-time compare); no host port | `test_api.py` (ledger), `verify_stack`: "ledger not reachable from host", 401 check | M ⏳ mTLS before production (ADR-0016) |
| S4 | An agent approves its own work | 3,4 | Approval trigger: approver = signed-in human, MFA on, reviewer role, not `system`; worker token cannot post; graph resumes only with `ReviewDecision` | `test_ledger_db.py` (agent-user), `test_api.py` (scope_denied), `test_graph.py` | L |
| T1 | Edit or delete a posted journal | 2 | Immutability triggers (even superuser); no UPDATE/DELETE grants; reversal-only | `test_ledger_db.py`, property test | L |
| T2 | Silent tampering by a DB superuser | 2 | Hash chains on ledger and audit; `verify_chain()` run by `verify_stack` | tamper tests, `verify_stack` chain checks | M ⏳ external anchoring of chain heads |
| T3 | Unbalanced or float-rounded books | 2,3 | Rules in code (Decimal) **and** DB (deferred constraint); floats rejected at API and rule packs | property tests (ledger, rules) | L |
| T4 | Tampered rule pack changes tax | 2 | Packs in Git (reviewed PRs), activation gate, content hash in results, citations required | `test_engine.py`, CI rule-pack gate | M ⏳ DB registry + approvals (Phase 1) |
| T5 | Malicious upload | 1,5 | ClamAV in stack (EICAR verified) | `verify_stack` | M ⏳ wired into upload flow (Phase 1) |
| R1 | User denies an action | all | Append-only, hash-chained audit in the same transaction (fail-closed); approvals snapshot name/role/time | `test_audit.py` | L (licence status `not_recorded` until GAP-REV-02) |
| I1 | Tenant A reads tenant B | 2 | RLS ENABLE+FORCE on every tenant table; transaction-local context; composite FKs; 404 not 403 | isolation suite, `verify_stack` RLS counts | L |
| I2 | Sensitive data sent to an LLM | 4,5 | Masking (emails, 9+ digit numbers) before the gateway; [MOCK] provider only in Phase 0 | `test_gateway.py` | M ⏳ provider DPAs (GAP-LEG-03) |
| I3 | Secrets leak via repo or logs | 6 | `.env` git-ignored; gitleaks over full history in CI; structlog masking of sensitive keys | CI `security`, `test_config_and_logging.py` | L |
| I4 | Services exposed on the network | 1 | All host ports bound to 127.0.0.1; ledger has none; Redis requires auth | `verify_stack` | L (local dev) |
| I5 | Agent state readable across tenants | 4 | Worker role confined to `agent_state`; tenant-prefixed thread ids; state holds references | `verify_stack`, `test_graph.py` | M (library tables have no RLS, ADR-0002) |
| D1 | Brute force / request floods | 1 | Lockout; body-size limits (413) | `test_errors.py` | M ⏳ rate limiting at the edge |
| D2 | Runaway agent cost / loops | 4 | Gateway call and token budgets | `test_gateway.py` | M (GAP-AGT-03 numbers) |
| E1 | Privilege escalation in the DB | 2 | No role has BYPASSRLS/superuser; runtime roles lack DELETE; app cannot create in `public` | `verify_stack` | L |
| E2 | Prompt injection makes an agent act | 5 | Document fenced as data, fence cannot be closed (property test); output schema `extra=forbid`; agents only propose; DB demands human approval | `test_gateway.py`, ADR-0004 | M (models remain fallible) |
| E3 | Compromised CI dependency | 6 | Read-only token; actions pinned to major versions; images pinned by version; Dependabot; trivy pinned to a known-good release (not `trivy-action`) | `ci.yml` | M ⏳ pin actions/images by digest |

## Follow-ups (tracked into Phase 1 backlog)

mTLS between services · chain-head anchoring to WORM storage · per-tenant envelope encryption
(ADR-0007) · edge rate limiting · DB rule-pack registry with approvals · upload scanning in the
flow · provider DPAs before any real LLM call · digest-pinned CI dependencies.
