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
