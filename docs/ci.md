# CI and branch protection (Step 0.11)

Workflow: `.github/workflows/ci.yml` (source copy in `setup/ci/ci.yml`). Runs on every pull request,
on pushes to `main` and manually (`workflow_dispatch`). Read-only token (`contents: read`).

| Job | What it proves | Fails when |
|---|---|---|
| `python` | ruff lint + format; `mypy --strict` for py-common, rule-engine, api, ledger; rule-pack activation gate; unit + Hypothesis property tests | any lint/type error, failing test, invalid or untested gated rule pack |
| `web` | `tsc --noEmit`, vitest, `next build` | type error, failing test, build error |
| `security` | gitleaks over the **whole git history**; `pip-audit`; `npm audit --omit=dev --audit-level=high` | a secret is found; a dependency has a known vulnerability |
| `stack` | builds every Docker image, scans the runtime images with trivy (CRITICAL, fix available), starts the full stack, runs `api-test` (alembic check, RLS tenant-isolation suite, auth, audit, ledger DB invariants, Money, rule engine) and `ledger-test`, then `verify_stack.py` | anything a developer would hit with the run-step scripts |

Each run generates a fresh `.env` with random secrets (`generate_env.py`); no real data is used.
Only the exact `[MOCK]` values in `.gitleaks.toml` are exempt from secret scanning.

## Branch protection for `main` (set once on GitHub)

GitHub → repository → **Settings → Branches → Add branch ruleset** (or *Add rule*), target `main`:

1. **Require a pull request before merging** — at least 1 approval [Recommended: 2 for ledger,
   rule-engine, migrations and security changes, matching the four-eyes principle].
2. **Require status checks to pass** and **require branches to be up to date**. Required checks:
   - `python (lint, types, unit, property, rule-packs)`
   - `web (typecheck, unit tests, build)`
   - `security (secrets, dependency audit)`
   - `stack (images, scan, migrations, integration, isolation, ledger, verify)`
3. **Block force pushes** and **restrict deletions**.
4. **Require conversation resolution before merging**.
5. Do not allow bypassing the above settings (include administrators).

The local `no-commit-to-branch` pre-commit hook already refuses direct commits to `main`.

## When a check is red

* `security` / dependency audit: update the dependency (Dependabot opens weekly PRs). If no fix
  exists yet, record the advisory, impact and review date in the PR — do not silence the audit.
* `security` / gitleaks: **rotate the secret first**, then remove it; history rewriting alone is
  not enough because the value must be treated as exposed.
* `stack`: the job prints the last 200 log lines of every container on failure.
