# AZINCO

AI-Powered Autonomous Accounting, Bookkeeping & Tax Management Platform.

> **AI prepares → deterministic code calculates → a qualified Reviewer of Record approves → the client receives deliverables.**

**Status: Phase 0 — Foundation (pre-alpha). Not production-ready.** Payment providers, AI models and OCR are **[MOCK]** or **[SANDBOX]** until the relevant phase exit gate passes.

## Repository layout

| Path | Purpose |
|---|---|
| `apps/web/` | Next.js (App Router, strict TypeScript, Tailwind) — client portal, Reviewer dashboard, Admin console |
| `services/api/` | FastAPI public REST API (auth, RBAC, tenants, tasks, documents, review, billing) |
| `services/ledger/` | Ledger Service — the only writer of journals (internal network only) |
| `services/worker/` | Background workers: document pipeline, LangGraph agents, Model Gateway |
| `packages/py-common/` | Shared Python: Pydantic schemas, `Money`, ids, audit client |
| `packages/rule-engine/` | Deterministic rule evaluator and calculators (tax split, FX, depreciation) |
| `rule-packs/` | Governed jurisdiction rule-pack sources (empty until content is sourced and approved) |
| `infra/docker/` | Dockerfiles and Docker Compose for local development |
| `infra/ci/` | CI helper scripts |
| `tests/e2e/` | Playwright end-to-end tests |
| `docs/blueprint/` | Requirements & Architecture Blueprint (Parts 1–5) |
| `docs/adr/` | Architecture Decision Records |
| `tools/playwright-mcp/` | Developer tooling: Playwright MCP setup for Claude |

## Non-negotiable rules (summary)

1. LLMs never produce authoritative figures; amounts, tax, FX and balances come from tested code.
2. Every journal line links to source evidence (document, page, field).
3. Journals balance (debits = credits) — enforced in code **and** in the database.
4. Posted entries are immutable; corrections are reversal + re-post.
5. Final statements, tax outputs and sign-offs require a human Reviewer of Record; agents can never approve.
6. Every action is written to an append-only, hash-chained audit log.
7. Tenant data is isolated with PostgreSQL Row-Level Security.
8. Domestic Pakistani payments are always called **Banking Channels** in client-facing text.
9. Money is `Decimal` / `NUMERIC(20,4)`; platform base currency is **PKR**.
10. Only synthetic test data in development. No secrets in git.

Full detail: `docs/blueprint/01-requirements-analysis.md` … `05-roadmap-and-phase0.md`.

## Prerequisites (developer machine)

- Git 2.40+
- Python 3.12+ and `pip`
- Node.js 20+ and npm
- Docker Desktop with WSL2 backend (Windows) or Docker Engine (Linux) — needed from Step 0.2

## First-time setup

```bash
git clone <your-repo-url> azinco
cd azinco
python infra/docker/generate_env.py   # creates .env with random secrets
python -m pip install pre-commit pytest
pre-commit install
pre-commit run --all-files
python infra/ci/check_structure.py
python -m pytest

# Local stack (Step 0.2) — see infra/docker/README.md
docker compose --env-file .env -f infra/docker/compose.yml up -d
python infra/docker/verify_stack.py
```

## Phase 0 progress

| Step | Title | Status |
|---|---|---|
| 0.1 | Repo structure & conventions | Done |
| 0.2 | Docker Compose stack | Done — verified 18/18 |
| 0.3 | FastAPI skeleton (`/health`, `/ready`) | Done — verified |
| 0.4 | Next.js web UI skeleton (home, live status) | Done — verified (web 3/3 checks) |
| 0.5 | PostgreSQL + Alembic + Money | Done — verified 26/26 |
| 0.6 | Tenant isolation (RLS) | Done (verified) |
| 0.7 | Auth, MFA & RBAC — sign in works | Done (verified) |
| 0.8 | Audit log (hash-chained, append-only) | Done (31/31 verified) |
| 0.9 | Ledger: database invariants (0.9a) + Ledger Service internal API (0.9b) | Done (38/38 verified) |
| 0.10 | Rule engine, Gateway, graph skeletons — 0.10a rule engine (done; verified by CI `stack`) · 0.10b gateway + graph (next) | In progress |
| 0.11 | CI pipeline — `.github/workflows/ci.yml` (python, web, security, stack), gitleaks, Dependabot; branch protection in docs/ci.md | Done (verify: first green PR) |
| 0.12 | Phase 0 governance pack | Pending |

## Contributing & security

See `CONTRIBUTING.md` and `SECURITY.md`.
