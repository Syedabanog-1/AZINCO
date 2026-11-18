# ADR-0008: Rule-pack format — YAML decision tables, pure evaluator, activation gate

| Field | Value |
|---|---|
| Status | Accepted (implemented in Step 0.10a) |
| Date | 2026-11-18 |
| Deciders | Engineer (Reviewer of Record owns pack content and promotion) |
| Requirements | FR-TAX-01, FR-TAX-07, FR-ADM-04, FR-AGT-06 |
| Base Standard | §2.4 (jurisdictions as configuration), §6.6 (two layers, versions, effective dates, citations, provisional ⇒ review), §8.2 (rule engine; tests block activation), §8.4 (traceability) |
| Label | [Source] requirements, [Recommended] format and mechanics |

## Context
Tax and bookkeeping rules differ per country and change over time. The Base Standard requires
them as versioned, cited configuration, never as code, with every figure traceable to the exact
rule version. AZINCO may not invent rates or thresholds (project principle 9).

## Decision
* A pack is a YAML decision table: `pack` metadata (jurisdiction, layer, version `YYYY.n`,
  status lifecycle of blueprint §2.11, `effective_from` / exclusive `effective_to`, owner,
  `review_due`, hit policy), declared `facts` with types, `rules` (conditions → outputs +
  citations) and `tests`.
* Library `packages/rule-engine` (`azinco_rules`): Pydantic schema, loader, `Registry.select()`
  by effective date, pure `evaluate()` returning outputs, rule ids, citations, version and a
  canonical `content_hash`.
* Safety by default: hit policy `unique` (ambiguity is an error), missing facts never match,
  floats rejected everywhere, unknown facts rejected, usable versions may not overlap.
* Activation gate in code and CI (`python -m azinco_rules check rule-packs`): gated statuses need
  rules, a citation on every rule, owner, review date, a test per decision table, all tests green.
* `provisional`/`under_review` results carry `needs_human_review = true` (§6.6).
* `rule-packs/` ships **empty**; tests use a [MOCK] pack for the non-country code `ZZ`.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. YAML decision tables + typed schema (chosen) | Readable by reviewers; diffable in Git; pure evaluation | Limited expressiveness (by design) |
| B. Rules as Python code | Unlimited logic | Reviewers cannot audit; violates "jurisdiction as data" |
| C. DMN / external rules engine | Standard notation | Heavy tooling; JVM; harder to test property-style |

## Consequences
* A DB registry (`rule_packs`, `rule_versions` with content hash, approvals) and the admin
  rule-pack manager follow in Phase 1; journal lines already have `rule_version_id` (ADR-0015).
* Calculators (tax split, FX, depreciation) are separate pure functions, added with their first
  consumer; they read rates only from evaluated packs.
* Real pack content waits for GAP-TAX-01..05 (sourced, cited, Reviewer-approved).
