# ADR-0005: Queue — Redis Streams with consumer groups and a dead-letter stream

| Field | Value |
|---|---|
| Status | Proposed (to be implemented with the first background job, Phase 1) |
| Date | 2026-11-18 |
| Base Standard | §11.2 (Redis + background workers), §7.1 (retries, checkpoints) |
| Label | [Recommended] |

## Decision (proposed)
Redis Streams (already in the stack, password-protected) with consumer groups; at-least-once
delivery with idempotency keys stored in PostgreSQL; bounded retries with backoff, then a
dead-letter stream surfaced on the admin dashboard. Long human waits do **not** sit in the queue —
they live in LangGraph checkpoints (ADR-0002).

## Options
| Option | Pros | Cons |
|---|---|---|
| A. Redis Streams (proposed) | Already deployed; simple; consumer groups + pending list | Durability depends on Redis persistence settings |
| B. Celery/RQ on Redis | Familiar | Extra framework; weaker visibility of pending work |
| C. Temporal / managed queue | Very durable | New infrastructure; revisit if needs grow |

## Open points
Redis AOF persistence settings for staging/production; retry limits per job type (GAP-AGT-03).
