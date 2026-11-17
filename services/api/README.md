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
| 0001 | schema `app`: `tenants`, `users`, `tenant_memberships`, `platform_roles`, 7 enums, `updated_at` trigger, least-privilege grants (no DELETE for runtime roles) |
