# azinco-api

AZINCO public REST API (FastAPI). See `docs/blueprint/02-architecture.md` §2.5.

```bash
pip install -e ".[dev]"
pytest
mypy
uvicorn azinco_api.main:create_app --factory --port 8000
```

## Database migrations (Step 0.5)

Alembic runs as the owner role `azinco_migrator` — never as the app role. In Docker the one-shot
`migrate` service runs `alembic upgrade head` before the API starts.

```bash
# local (needs AZINCO_DB_MIGRATOR_PASSWORD and POSTGRES_* in the environment)
pip install -e ../../packages/py-common -e ".[dev]"
alembic upgrade head      # apply
alembic check             # fails if models and migrations drift
alembic downgrade -1      # roll back one revision
```

| Revision | Content |
|---|---|
| 0006 | Schema `agent_state` for LangGraph checkpoints; `azinco_worker` may create tables only there (ADR-0002) |
| 0005 | Ledger: `app.entities`, `app.approvals`, schema `ledger` (accounts, periods, journals, lines), invariants L1-L9 as DB triggers, post/reverse/discard/lock/reopen functions, per-tenant hash chain (ADR-0015) |
| 0004 | Audit log: schema `audit`, hash-chained `audit_events`, `append_event()` / `verify_chain()`, append-only triggers (ADR-0012) |
| 0003 | Auth: `sessions`, `email_verification_tokens`, lockout/MFA columns, SECURITY DEFINER auth functions (ADR-0006) |
| 0002 | Row-Level Security: ENABLE+FORCE on all `app` tables, `app.current_tenant_id()` / `app.current_user_id()`, per-command policies (ADR-0003) |
| 0001 | schema `app`: `tenants`, `users`, `tenant_memberships`, `platform_roles`, 7 enums, `updated_at` trigger, least-privilege grants (no DELETE for runtime roles) |

## Authentication (Step 0.7, ADR-0006)

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/register` | Create a pending account; sends a confirmation e-mail (Mailpit locally). Same answer whether or not the e-mail exists |
| `POST /api/v1/auth/verify-email` | Activate the account with the e-mailed token |
| `POST /api/v1/auth/login` | E-mail + password (+ 6-digit code when MFA is on). Sets `azinco_session` (HttpOnly) and `azinco_csrf` |
| `POST /api/v1/auth/logout` | Revoke the session (needs `X-CSRF-Token`) |
| `GET /api/v1/me` | Current user, workspaces, roles and permissions |
| `POST /api/v1/auth/mfa/setup` / `confirm` | TOTP enrolment (QR code + manual key) |
| `GET /api/v1/tenants/{id}` | Example of the full chain: session → MFA policy → RBAC → RLS |

## Audit log (Step 0.8, ADR-0012)

Every auth action is written to `audit.audit_events` in the same transaction (if the audit write
fails, the action fails). Rows are hash-chained per tenant and can never be updated or deleted.

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/tenants/{id}/audit-events?limit=50&before_seq=` | Newest-first page of the tenant's audit trail (`audit.read`, MFA) |
| `GET /api/v1/tenants/{id}/audit-events/verify` | Recompute the hash chain: `{events, ok, first_bad_seq}` |

From code: `await azinco_api.audit.record(session, "domain.action", tenant_id=..., details={...})`.
Sensitive keys in `details` are masked automatically.

## [MOCK] Test workspace (local/CI only)

Client onboarding (KYC/AML, engagement letter, advance payment) arrives in Phase 1. Until then,
create a synthetic workspace for a verified account (refuses to run outside `AZINCO_ENV=local/ci`;
the name is prefixed `[MOCK]` and a `tenant.created` audit event records `"mock": true`):

```
docker compose --env-file .env -f infra/docker/compose.yml exec api \
  python -m azinco_api.devtools.seed_workspace --email you@example.com --name "Demo Traders"
```
