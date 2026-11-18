# services/ledger — AZINCO Ledger Service

The **only** writer of journals (Base Standard §8.2, §8.4; blueprint AP-2). Internal network only:
the container publishes no port to the host.

* Rules are enforced twice: in code (`azinco_ledger/domain.py`, Decimal, before any write) and in
  PostgreSQL (migration `0005_ledger.py`, ADR-0015). Base-currency amounts are always computed by
  the service (`round_half_up(amount × rate, 4)`); callers can never send them.
* Posting, reversal posting and period reopening need a **reviewer approval id**. The database
  checks the approver (signed-in human, MFA on, reviewer role) and allows each approval once.
* Every action writes an audit event in the same transaction (ADR-0012).

## Internal API (`http://ledger:8100`, ADR-0016)

Headers on every call: `Authorization: Bearer <service token>`, `X-Tenant-Id`, `X-Actor-Id`.

| Method | Path | Token | Purpose |
|---|---|---|---|
| POST | `/internal/ledger/accounts` | API | Add an account to an entity's chart |
| POST | `/internal/ledger/periods` | API | Add an accounting period (no overlaps) |
| POST | `/internal/ledger/periods/{id}/lock` | API | Lock a period |
| POST | `/internal/ledger/periods/{id}/reopen` | API | Reopen with `{approval_id}` |
| POST | `/internal/ledger/drafts` | API, worker | Create a balanced draft journal |
| POST | `/internal/ledger/post` | API | Post a draft with `{journal_id, approval_id}` |
| POST | `/internal/ledger/reverse` | API | Create the mirrored reversal draft |
| POST | `/internal/ledger/discard` | API, worker | Discard a draft (never deleted) |
| GET | `/internal/ledger/journals/{id}` | API, worker | Journal with lines |
| GET | `/internal/ledger/verify` | API, worker | Recompute the tenant's hash chain |
| GET | `/health`, `/ready` | — | Probes |

Money in requests and responses is a **string** (`"1500.50"`); JSON floats are rejected.
Errors are `application/problem+json` with a stable `code` (`unbalanced`, `fx_rate_not_one`,
`not_authorised`, `ledger_rule`, `period_overlap`, `unknown_reference`, `scope_denied`, …).

## Settings (environment)

`AZINCO_DB_LEDGER_PASSWORD`, `AZINCO_LEDGER_API_TOKEN` (≥ 32 chars), optional
`AZINCO_LEDGER_WORKER_TOKEN` (different from the API token), `POSTGRES_HOST/PORT/DB`.

## Tests

`docker compose ... --profile test run --rm ledger-test` → `LEDGER-TESTS-OK`
(domain rules + Hypothesis properties, and end-to-end tests against PostgreSQL).
