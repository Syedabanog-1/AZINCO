# ADR-0016: Ledger Service as a separate internal deployable with scoped service tokens

| Field | Value |
|---|---|
| Status | Accepted (implemented in Step 0.9b) |
| Date | 2026-11-18 |
| Deciders | Engineer |
| Requirements | FR-LED-03, FR-LED-04, FR-LED-05, NFR-SEC-04 |
| Base Standard | §8.2 (a small FastAPI Ledger Service is the only writer), §8.4, §7.7 |
| Blueprint | AP-2 (single writer; agents only draft), §2.3 runtime containers, §3.5 internal API |
| Label | [Source] single writer, [Recommended] token scopes and network isolation |

## Context
Only the Ledger Service may write journals, and agents may create **drafts** but never post
(blueprint AP-2, §2.6 tool table: `ledger.post` is "callable only by the API on behalf of a human
approval"). The service must be reachable by the API and, later, by the worker - and by nothing else.

## Decision
* `services/ledger` is its own package and container (`azinco-ledger`), FastAPI on port 8100,
  **no host port published**; it connects to PostgreSQL as `azinco_ledger` only.
* Callers authenticate with a bearer **service token**, compared in constant time:
  * `AZINCO_LEDGER_API_TOKEN` - all operations (accounts, periods, drafts, post, reverse,
    discard, lock, reopen, reads);
  * `AZINCO_LEDGER_WORKER_TOKEN` - drafts, discard and reads only (`403 scope_denied` otherwise).
  Tokens are ≥ 32 characters, must differ, live only in `.env` / a secret store.
* Every request carries `X-Tenant-Id` and `X-Actor-Id`; the service sets them transaction-locally,
  so RLS and the database invariants (ADR-0015) apply to every statement.
* Posting still requires a reviewer approval id; the token alone can never post.
* Rules are checked in code first (`domain.py`, Decimal; precise error codes), then by the
  database. A property test proves code and PostgreSQL round base amounts identically.
* Money crosses the API as strings; JSON floats are rejected.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. Separate container + scoped tokens (chosen) | Matches BS §8.2; agents physically cannot post; small blast radius | One more container; tokens to rotate |
| B. Ledger as a module inside the API | Simpler | Any API bug or agent tool path could reach posting code |
| C. mTLS between services | Strong identity | Certificate tooling not justified in local dev; planned for staging/production [Recommended] |

## Consequences
* The public API's review module (Phase 1) will call `/internal/ledger/post` after a reviewer
  approves; the worker gets only the worker token.
* Token rotation: change `.env`, restart `ledger`, `api`, `worker`. mTLS or a service mesh replaces
  bearer tokens before production (tracked for the security review exit gate).
