# infra/docker — local development stack (Step 0.2)

Synthetic data only. All ports bind to `127.0.0.1`. Nothing here is production configuration.

| Service | Image | Port(s) | Purpose |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | System of record + pgvector (RAG) |
| `redis` | `redis:7-alpine` | 6379 | Queues (Redis Streams), rate limits — password required |
| `storage` | `cgr.dev/chainguard/minio:latest` (configurable `S3_IMAGE`) | 9000 API, 9001 console | **[MOCK]** S3-compatible object storage |
| `storage-init` | `amazon/aws-cli` | — | One-shot: creates `azinco-documents` (versioned) and `azinco-archive` (object lock) |
| `clamav` | `clamav/clamav:stable` | 3310 | Virus scanning of uploads (BS §4.2(4)) |
| `mailpit` | `axllent/mailpit` | 1025 SMTP, 8025 UI | Captures dev e-mail; nothing is really sent |

## Start (Windows PowerShell or bash, from the repository root)

```powershell
python infra/docker/generate_env.py          # creates .env with random secrets (once)
docker compose --env-file .env -f infra/docker/compose.yml up -d
docker compose --env-file .env -f infra/docker/compose.yml ps
python infra/docker/verify_stack.py           # all checks should PASS
```

First start: ClamAV downloads virus signatures (≈ 3–5 minutes, ~1 GB RAM). Re-run `verify_stack.py` until `clamav healthy` passes.

## Stop / reset

```powershell
docker compose --env-file .env -f infra/docker/compose.yml stop          # keep data
docker compose --env-file .env -f infra/docker/compose.yml down          # remove containers, keep volumes
docker compose --env-file .env -f infra/docker/compose.yml down -v       # DELETE all local data (roles re-created on next up)
```

## Database roles (created once by `postgres/init/`)

| Role | Purpose | Superuser | BYPASSRLS | Owns tables |
|---|---|---|---|---|
| `azinco_migrator` | Alembic migrations only; owns DB & schemas | no | no | yes |
| `azinco_app` | Public API | no | no | no |
| `azinco_worker` | Agents / pipelines | no | no | no |
| `azinco_ledger` | Ledger Service | no | no | no |
| `azinco_audit` | Audit writer (INSERT-only from Step 0.8) | no | no | no |
| `azinco_readonly` | Reporting; `default_transaction_read_only = on` | no | no | no |

Because runtime roles neither own tables nor bypass RLS, Row-Level Security (Step 0.6) always applies to them.

## Object storage note (MinIO)

MinIO stopped publishing community Docker images in October 2025 and archived the community edition.
AZINCO uses only the standard S3 API, so the server is replaceable:

| Option | `S3_IMAGE` value | Notes |
|---|---|---|
| Default | `cgr.dev/chainguard/minio:latest` | Maintained, patched MinIO build (free `latest` tag) |
| Alternative | any S3-compatible image (e.g. RustFS, SeaweedFS, Garage) | Adjust `command`/env in `compose.yml`; `storage-init` works unchanged (aws-cli) |

Production uses managed S3 with KMS envelope encryption (ADR-0007). Application-level per-tenant encryption does not depend on the local storage server.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `set POSTGRES_SUPERUSER in .env` | Run `python infra/docker/generate_env.py` |
| Port already in use | Change `POSTGRES_PORT`, `REDIS_PORT`, … in `.env` |
| `storage` image pull denied | Set another `S3_IMAGE` (see table above) |
| `clamav` stays `starting` | Wait for signature download; check `docker compose ... logs clamav` |
| Changed DB passwords in `.env` but login fails | Passwords apply only on first volume creation → `down -v` then `up -d` |
| Init `.sh` script "permission denied" | Already handled: the entrypoint sources non-executable scripts |
