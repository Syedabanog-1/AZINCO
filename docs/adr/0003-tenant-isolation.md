# ADR-0003: Tenant isolation with PostgreSQL Row-Level Security

| Field | Value |
|---|---|
| Status | Accepted (implemented in Step 0.6) |
| Date | 2026-11-17 |
| Deciders | Owner, Engineer |
| Requirements | NFR-SEC-01, FR-IAM-02 |
| Base Standard | BS §8.4, §12, §14 ("data leak between clients") |
| Label | [Source] requirement, [Recommended] mechanism |

## Context
Every client is a tenant whose financial data must never be visible to another tenant, even if
application code has a bug (a missing `WHERE tenant_id = ...`).

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. Database per tenant | Strongest separation | Heavy ops, migrations ×N, costly for SMEs |
| B. Schema per tenant | Good separation | Migrations ×N, catalog bloat, harder pooling |
| C. Shared schema + `tenant_id` + RLS | One schema, one migration path, DB-enforced filter | Requires disciplined context handling |
| D. Shared schema, app-only filtering | Simple | One forgotten filter = data leak |

## Decision
Option C.
* Every tenant-owned table has `tenant_id`; RLS is **ENABLE**d and **FORCE**d (applies to the owner too).
* Context is set per transaction with `set_config('app.tenant_id', ..., true)` (transaction-local) via
  `azinco_api.db.tenancy.tenant_session`; it cannot leak to the next request on a pooled connection.
* `app.current_tenant_id()` returns NULL without context → policies match nothing → zero rows, writes refused.
* Runtime roles are not owners and have no `BYPASSRLS`; migrations run as `azinco_migrator`.
* New tenants are created "context first": the application generates the id, sets it as context, inserts.
* `users` are platform-level: visible to themselves or to the tenant they are a (non-expired) member of.

## Consequences
* Positive: isolation enforced by PostgreSQL; a forgotten filter returns nothing instead of leaking.
* Negative: every DB access must go through `tenant_session`; cross-tenant admin views need dedicated,
  audited paths (Admin console, later).
* Guard rails: CI test fails if any table in schema `app` lacks ENABLE+FORCE RLS or a policy;
  `verify_stack.py` checks RLS state and that the app role sees 0 rows without context.

## Validation
`services/api/tests/test_tenant_isolation.py` (21 cases): no-context reads/writes, cross-tenant
read/update/insert/move, user visibility, expired memberships, self-granted platform roles,
pooled-connection leak, rollback, read-only role.
