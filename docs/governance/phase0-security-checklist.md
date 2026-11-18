# Phase 0 security checklist and acceptance status

| Field | Value |
|---|---|
| Base Standard | §12 (security), §15 (phase exit: golden-set targets, Reviewer of Record sign-off, security review) |
| Source of items | Roadmap Phase 0 "Security checks" and "Acceptance criteria" |
| Last updated | 2026-11-18 (Step 0.12) |

✅ done with evidence · 🟡 partial · ⏳ open (owner action or later step)

## Security checks

| Check | Status | Evidence / note |
|---|---|---|
| Secrets scan (gitleaks, full history) | ✅ | CI `security`; history scan 2026-11-18: no leaks; `.gitleaks.toml` allows only [MOCK] values |
| Dependency audit (pip-audit, npm audit) | ✅ | CI `security` green on runs #1 and #14 |
| SAST — Python | ✅ | ruff `S` rules (flake8-bandit equivalent) on all Python packages, CI `python` |
| SAST — web (eslint security rules) | ⏳ | ESLint not configured in `apps/web` yet — first web task of Phase 1 |
| Container scan (trivy) | ✅ | CI `stack` run #14: no CRITICAL vulnerability with an available fix (trivy 0.76.2) |
| Threat model (STRIDE) reviewed | 🟡 | `threat-model.md` drafted; review signature pending |
| MFA enforced for staff, reviewer, platform roles | ✅ | `test_auth_flow.py`, RBAC `MFA_REQUIRED_TENANT_ROLES` |
| DB roles: no superuser / BYPASSRLS; no DELETE for runtime roles | ✅ | `verify_stack` (39/39 on 2026-11-18) |
| Services bound to localhost; ledger not exposed | ✅ | `verify_stack` |
| Agents cannot write the books or approve | ✅ | `test_ledger_db.py`, ledger `test_api.py`, worker `test_graph.py`, `verify_stack` worker check |
| CI supply chain | 🟡 | read-only token, pinned versions, Dependabot; ⏳ digest pinning |

## Phase 0 acceptance criteria

| # | Criterion | Status | Evidence / owner |
|---|---|---|---|
| 1 | `docker compose up` brings all services healthy | ✅ | run-step-0.10b log: 39/39 |
| 2 | CI green on all gates | ✅ | CI run #14 on `main` (f6111da), 2026-11-18: python, web, security, stack all green |
| 3 | Isolation suite: tenant A cannot read/write tenant B on every tenant table | ✅ | `test_tenant_isolation.py`, ledger/audit RLS tests |
| 4 | Unbalanced journal and update of a posted journal rejected **by the database** | ✅ | `test_ledger_db.py` incl. property tests |
| 5 | Every API mutation produces an audit event and the chain verifies | ✅ | auth + ledger mutations audited in-transaction; `verify_stack` chains (new mutations must keep this) |
| 6 | ADRs approved | ⏳ | ADR-0001…0016 written; owner approval in `phase0-signoff.md` |
| 7 | Delivery-mode matrix + legal review recorded | 🟡 | Template ✅; legal review ⏳ GAP-LEG-01 (counsel) |
| 8 | Reviewer of Record named and licence recorded | ⏳ | DEC-13 (owner) |
| 9 | Security review signed | ⏳ | This checklist + threat model → reviewer signature |
| G | Golden-set framework and first synthetic set exist | 🟡 | `golden-set-plan.md` ✅; first synthetic set + runner ⏳ (first Phase 1 task) |

**Phase 0 is not closed** until rows 6, 7, 8, 9 and G are complete and signed. Nothing here
means production readiness.
