# Architecture Decision Records

Template: `0000-template.md`. Number ADRs sequentially; never edit an Accepted ADR — supersede it.

| ADR | Title | Status |
|---|---|---|
| 0001 | Repo & service topology (monorepo, modular-monolith API + ledger + worker) | Proposed (Step 0.12) |
| 0002 | Orchestration framework (LangGraph + Postgres checkpointer) | Proposed |
| 0003 | Tenant isolation (shared schema + RLS + `SET LOCAL`) | Proposed |
| 0004 | Model Gateway | Proposed |
| 0005 | Queue (Redis Streams) | Proposed |
| 0006 | Authentication — FastAPI-native (option a) | Proposed — **assumed** pending owner confirmation (DEC-11) |
| 0007 | Encryption & keys | Proposed |
| 0008 | Rule-pack format | Proposed |
| 0009 | Money & FX — Decimal, NUMERIC(20,4), base PKR | Proposed (DEC-12 resolved) |
| 0010 | OCR engine | Open (spike in Phase 1) |
| 0011 | Payment adapter & "Banking Channels" | Proposed |
| 0012 | Audit store | Proposed |
| 0013 | Hosting & region | Open (DEC-10) |
| 0014 | Local object storage image (MinIO community images discontinued Oct 2025 → Chainguard MinIO build, swappable via `S3_IMAGE`) | Proposed (Step 0.2) |

Owner decisions log:

| Decision | Value | Date | Status |
|---|---|---|---|
| DEC-12 Base currency | PKR | 2026-11-17 | Confirmed by owner |
| DEC-01 First international market | UK | 2026-11-17 | Assumed — awaiting confirmation |
| DEC-11 Auth approach | (a) FastAPI-native | 2026-11-17 | Assumed — awaiting confirmation |
