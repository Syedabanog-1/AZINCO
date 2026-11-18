# ADR-0015: Ledger invariants enforced in PostgreSQL, single writer, human approval to post

| Field | Value |
|---|---|
| Status | Accepted (implemented in Step 0.9a; service layer follows in 0.9b) |
| Date | 2026-11-18 |
| Deciders | Engineer (Reviewer of Record to confirm the approval rules) |
| Requirements | FR-LED-03, FR-LED-04, FR-LED-05, FR-LED-09, FR-LED-15, NFR-SEC-04 |
| Base Standard | §6.4 (posting standards), §6.5 (period close), §8.2 (Ledger Service), §8.4 (DB constraints), §8.7 (approval records) |
| Label | [Source] invariants, [Recommended] mechanisms marked below |

## Context
Project principles 1–5: AI prepares, code calculates, a qualified human approves; journals always
balance; posted entries are immutable and corrected only by reversal. The Base Standard (§8.4) asks
for these rules in the database as well as in code, so that a bug in one service, a compromised
agent or a hand-written SQL statement still cannot leave the books wrong.

## Decision
Migration `0005_ledger.py` creates schema `ledger` (accounts, periods, journals, journal_lines,
consumed_approvals) plus `app.entities` and `app.approvals`, and enforces blueprint invariants:

| # | Rule | How the database enforces it |
|---|---|---|
| L1 | Balanced | Deferred constraint triggers at COMMIT: ≥ 2 lines, Σ base debit = Σ base credit; single-currency journals also balance in transaction currency |
| L2 | Posted immutable | Lines: no UPDATE/DELETE for anyone (trigger). Journals: content never changes; status changes only inside ledger functions (trigger + no UPDATE grant) |
| L3 | Reversal only | `ledger.create_reversal()` mirrors every line; `reverses_id` unique; original becomes `reversed` when the reversal is posted |
| L4 | Evidence | `evidence_type` required; `extraction` lines need document + field ids; tax-coded lines need a rule version |
| L5 | Periods | Posting needs an `open`/`reopened` period covering the date; periods never overlap (`btree_gist` exclusion [Recommended]); reopening needs an approval |
| L6 | Human approver | `app.approvals` insert trigger: approver = signed-in user, active, MFA on, not a `system` user, role `reviewer`/`second_reviewer` in the tenant; role and name are snapshotted. Approvals are immutable and single-use [Recommended] |
| L7 | Money | NUMERIC(20,4) amounts, NUMERIC(20,10) rates; `base = round(amount × rate, 4)`; functional-currency lines use rate 1 |
| L8 | Tenancy | RLS ENABLE + FORCE on all tables; composite FKs `(tenant_id, entity_id, …)` stop cross-entity accounts |
| L9 | Tamper evidence | Per-tenant hash chain over each posted journal and its lines; `ledger.verify_chain()` |

Privileges: only `azinco_ledger` (the Ledger Service) inserts accounts, periods, drafts and lines,
and executes `post_journal`, `create_reversal`, `discard_journal`, `lock_period`, `reopen_period`.
`azinco_app` inserts approvals (the reviewer's click) and entities. Every ledger function writes an
audit event in the same transaction (ADR-0012).

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. Rules in DB **and** service (chosen) | Defence in depth; matches BS §8.4 | Rules written twice (SQL + Python) — mitigated by tests on both |
| B. Rules in service code only | One place to change | Any other writer (bug, script, agent) can corrupt the books |
| C. Event-sourced ledger store | Natural history | New infrastructure; harder reporting; not needed at this scale |

## Consequences
* Drafts are never deleted; abandoned drafts become `discarded` [Recommended].
* Approver licence status is stored as `not_recorded` until reviewer licence verification exists
  (Phase 1, GAP for licence registry). Final statements and tax sign-off must later require
  `verified` (§8.7) — not enforced yet, recorded here so it is not forgotten.
* Four-eyes (second reviewer for high-value work) is not yet enforced at posting; added with the
  confidence/risk policy (Phase 2).
* No tax rates, accounts templates or thresholds are seeded: those come from sourced rule packs.
