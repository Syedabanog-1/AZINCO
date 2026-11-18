# Architecture Decision Records

Template: `0000-template.md`. Number ADRs sequentially; never edit an Accepted ADR — supersede it.

| ADR | Title | Status |
|---|---|---|
| 0001 | Repo & service topology (monorepo, modular-monolith API + ledger + worker) | Proposed (Step 0.12) |
| 0002 | Orchestration framework (LangGraph + Postgres checkpointer) | Proposed |
| [0003](0003-tenant-isolation.md) | Tenant isolation (shared schema + RLS + transaction-local context) | **Accepted** (Step 0.6) |
| 0004 | Model Gateway | Proposed |
| 0005 | Queue (Redis Streams) | Proposed |
| [0006](0006-authentication.md) | Authentication — FastAPI-native sessions, Argon2id, TOTP MFA | **Accepted** (Step 0.7) |
| 0007 | Encryption & keys | Proposed |
| [0008](0008-rule-pack-format.md) | Rule-pack format — YAML decision tables, pure evaluator, activation gate | **Accepted** (Step 0.10a) |
| 0009 | Money & FX — Decimal, NUMERIC(20,4), base PKR | Proposed (DEC-12 resolved) |
| 0010 | OCR engine | Open (spike in Phase 1) |
| 0011 | Payment adapter & "Banking Channels" | Proposed |
| [0012](0012-audit-store.md) | Audit store — append-only, hash-chained Postgres table | **Accepted** (Step 0.8) |
| 0013 | Hosting & region | Open (DEC-10) |
| [0015](0015-ledger-invariants-in-database.md) | Ledger invariants in PostgreSQL, single writer, human approval to post | **Accepted** (Step 0.9a) |
| [0016](0016-ledger-service-internal-api.md) | Ledger Service: separate internal deployable, scoped service tokens | **Accepted** (Step 0.9b) |
| 0014 | Local object storage image (MinIO community images discontinued Oct 2025 → Chainguard MinIO build, swappable via `S3_IMAGE`) | Proposed (Step 0.2) |

Owner decisions log:

| Decision | Value | Date | Status |
|---|---|---|---|
| DEC-12 Base currency | PKR primary; reporting in PKR **and** USD | 2026-11-17 | Confirmed by owner (updated same day) |
| DEC-14 International payments | **Stripe** only (PayPal removed). Client label: "Card" with "processed by Stripe". Adapter stays provider-agnostic | 2026-11-17 | Confirmed by owner |
| DEC-01 First international market | UK | 2026-11-17 | Assumed — awaiting confirmation |
| DEC-11 Auth approach | (a) FastAPI-native | 2026-11-17 | Assumed — awaiting confirmation |
