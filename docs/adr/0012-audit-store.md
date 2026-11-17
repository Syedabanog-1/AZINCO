# ADR-0012: Audit store — append-only, hash-chained table in PostgreSQL

| Field | Value |
|---|---|
| Status | Accepted (implemented in Step 0.8) |
| Date | 2026-11-17 |
| Deciders | Engineer (Reviewer of Record to confirm retention per jurisdiction) |
| Requirements | FR-ADM-01, NFR-SEC-04 (foundation for FR-ADM-02, FR-LED-15, FR-ARC-01) |
| Base Standard | BS §7.3(15) (Audit and Logging Service), §8.7 (approvals recorded), §12 (immutable audit trail) |
| Label | [Source] requirement, [Recommended] mechanism |

## Context
Every action — human, agent or system — must be written to an immutable audit log (project
principle 10). The log must be tenant-isolated, provably untampered, and written in the same
transaction as the change it describes, so an action can never succeed without its audit record.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. Postgres table, append-only + per-stream hash chain (chosen) | Same transaction as the business write (fail-closed); RLS reuse; simple backups; tamper-evident | Superuser can still alter rows (but verification detects it) |
| B. Separate log service / event stream (Kafka, Loki) | Scales independently | Two-phase write problem; audit can be lost when the business write succeeds |
| C. Managed ledger DB (QLDB-style) | Cryptographic verification built in | Vendor lock-in, data residency, extra cost; QLDB itself was retired |

## Decision
* Schema `audit`, table `audit.audit_events`, one hash chain **per stream** (stream = tenant, or a
  fixed zero UUID for platform-level events). `row_hash = sha256(prev_hash || canonical_text(row))`;
  the first row of a stream links to 32 zero bytes.
* Writes only through `audit.append_event(...)` (SECURITY DEFINER, owned by `azinco_migrator`). It
  takes a per-stream advisory transaction lock, so concurrent writers produce one unbroken chain.
* Runtime roles have **no** INSERT/UPDATE/DELETE on the table. Triggers reject UPDATE, DELETE and
  TRUNCATE for every role, including the superuser.
* `audit.verify_chain(tenant)` recomputes the chain and returns the first broken sequence number.
  `verify_stack.py` runs it for every stream; the API exposes it at
  `GET /api/v1/tenants/{id}/audit-events/verify` (permission `audit.read`, MFA required).
* RLS: a tenant sees only its own stream. Platform-level events (no tenant) are visible only to the
  superuser for now [Recommended: a platform-auditor endpoint in Phase 1].
* The Python writer `azinco_api.audit.record()` masks sensitive keys (passwords, tokens, keys) in
  `details` before writing, and attaches the request ID from structured logging.
* Actions are dotted lower-case names (`auth.login.failed`), checked by a CHECK constraint.

## Events wired in Step 0.8
`user.registered`, `user.email_verified`, `auth.email_verification.failed`,
`auth.register.duplicate_email`, `auth.login.succeeded`, `auth.login.failed`, `auth.login.blocked`,
`auth.logout`, `auth.mfa.setup_started`, `auth.mfa.confirm_failed`, `auth.mfa.enabled`.
Ledger, approval, billing and agent events are added with their services (Steps 0.9+).

## Consequences
* An attacker with database superuser rights can disable the trigger and edit a row, but cannot do so
  without `verify_chain` reporting it. [Recommended, Phase 1] Periodically anchor each stream's latest
  `row_hash` outside the database (signed, in WORM object storage) so that rewriting a whole chain is
  also detectable.
* Retention: rows are never deleted by the application. Legal retention periods per jurisdiction are
  **not yet decided** — gap recorded for the Reviewer of Record and legal counsel (no invented periods).
* Audit volume grows with activity; partitioning by month is a [Recommended] Phase 2 task.
