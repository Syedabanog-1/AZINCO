# Architecture Decision Records

Template: `0000-template.md`. Number ADRs sequentially; never edit an Accepted ADR — supersede it.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-repo-and-service-topology.md) | Repo & service topology (monorepo, modular-monolith API + ledger + worker) | **Accepted** (Step 0.12) |
| [0002](0002-orchestration-langgraph.md) | Orchestration — LangGraph, Postgres checkpointer, human interrupts | **Accepted** (Step 0.10b) |
| [0003](0003-tenant-isolation.md) | Tenant isolation (shared schema + RLS + transaction-local context) | **Accepted** (Step 0.6) |
| [0004](0004-model-gateway.md) | Model Gateway — model-agnostic, fenced untrusted data, masking, typed output | **Accepted** (Step 0.10b) |
| [0005](0005-queue.md) | Queue — Redis Streams, consumer groups, dead-letter stream | Proposed (Phase 1) |
| [0006](0006-authentication.md) | Authentication — FastAPI-native sessions, Argon2id, TOTP MFA | **Accepted** (Step 0.7) |
| [0007](0007-encryption-and-keys.md) | Encryption & keys | **Accepted** for Phase 0; envelope encryption Proposed (Phase 1) |
| [0008](0008-rule-pack-format.md) | Rule-pack format — YAML decision tables, pure evaluator, activation gate | **Accepted** (Step 0.10a) |
| [0009](0009-money-and-fx.md) | Money & FX — Decimal, NUMERIC(20,4), base PKR | **Accepted** |
| [0010](0010-ocr-engine.md) | OCR engine | Open (spike in Phase 1, DEC-09) |
| [0011](0011-payment-adapter.md) | Payment adapter — "Banking Channels" + Card via Stripe, funds_handling | Proposed (Phase 1) |
| [0012](0012-audit-store.md) | Audit store — append-only, hash-chained Postgres table | **Accepted** (Step 0.8) |
| [0013](0013-hosting-and-region.md) | Hosting & region | Open (DEC-10) |
| [0015](0015-ledger-invariants-in-database.md) | Ledger invariants in PostgreSQL, single writer, human approval to post | **Accepted** (Step 0.9a) |
| [0016](0016-ledger-service-internal-api.md) | Ledger Service: separate internal deployable, scoped service tokens | **Accepted** (Step 0.9b) |
| [0014](0014-local-object-storage-image.md) | Local object storage image (Chainguard MinIO, swappable via `S3_IMAGE`) | **Accepted** (Step 0.2) |

Owner decisions log:

| Decision | Value | Date | Status |
|---|---|---|---|
| DEC-12 Base currency | PKR primary; reporting in PKR **and** USD | 2026-11-17 | Confirmed by owner (updated same day) |
| DEC-14 International payments | **Stripe** only (PayPal removed). Client label: "Card" with "processed by Stripe". Adapter stays provider-agnostic | 2026-11-17 | Confirmed by owner |
| DEC-01 First international market | UK | 2026-11-18 | **Confirmed by owner** |
| DEC-11 Auth approach | (a) FastAPI-native (ADR-0006) | 2026-11-18 | **Confirmed by owner** |
| DEC-13 Reviewer of Record | Aun Ali Zaidi, **FCMA** — Chartered Institute of Management Accountants (**CIMA**, UK); membership no. `######` (masked — kept outside the public repository); **certificate inspected and verified by owner 2026-11-18**, evidence held outside the repository | 2026-11-18 | Confirmed; licence status `verified` (BS §8.7). Which delivery modes this credential supports: legal review GAP-LEG-01 |
