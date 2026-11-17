#!/usr/bin/env bash
# AZINCO Step 0.2 — database roles (runs once, as bootstrap superuser, on an empty volume).
#
# Role model (Blueprint Part 3 §3.1, ADR-0003):
#   azinco_migrator  owns the database and all schemas/tables; used ONLY by Alembic.
#   azinco_app       public API            } none of these is superuser, none has BYPASSRLS,
#   azinco_worker    agents / pipelines    } none owns tables -> Row-Level Security always applies.
#   azinco_ledger    Ledger Service        }
#   azinco_audit     audit writer (INSERT-only, granted in Step 0.8)
#   azinco_readonly  reporting / support read access
# Table/schema grants are added by Alembic migrations, never here.
# NOTE: the postgres entrypoint *sources* this file when it is not executable (common on
# Windows mounts), so we avoid `set -u`, which would leak into the entrypoint.
set -eo pipefail

: "${POSTGRES_USER:?}" "${POSTGRES_DB:?}"
: "${AZINCO_DB_MIGRATOR_PASSWORD:?}" "${AZINCO_DB_APP_PASSWORD:?}" "${AZINCO_DB_WORKER_PASSWORD:?}"
: "${AZINCO_DB_LEDGER_PASSWORD:?}" "${AZINCO_DB_AUDIT_PASSWORD:?}" "${AZINCO_DB_READONLY_PASSWORD:?}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v db="$POSTGRES_DB" \
  -v migrator_pw="$AZINCO_DB_MIGRATOR_PASSWORD" \
  -v app_pw="$AZINCO_DB_APP_PASSWORD" \
  -v worker_pw="$AZINCO_DB_WORKER_PASSWORD" \
  -v ledger_pw="$AZINCO_DB_LEDGER_PASSWORD" \
  -v audit_pw="$AZINCO_DB_AUDIT_PASSWORD" \
  -v readonly_pw="$AZINCO_DB_READONLY_PASSWORD" \
  --file "${AZINCO_ROLES_SQL:-/docker-entrypoint-initdb.d/sql/roles.sql}"
