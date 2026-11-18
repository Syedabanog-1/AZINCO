# Rule-pack governance SOP

| Field | Value |
|---|---|
| Base Standard | §2.4 (jurisdictions as configuration), §6.6 (two layers, versions, effective dates, citations, provisional ⇒ review), §8.2 (pack tests block activation) |
| Implements | ADR-0008; `packages/rule-engine`; CI gate `python -m azinco_rules check rule-packs` |
| Owner | Reviewer of Record (content) · Platform Admin (publication) · Engineer (tooling) |

## Principles

1. **No invented content.** Every rate, threshold, deadline and mapping comes from an official,
   current source, cited on the rule (title, reference, section, retrieval date).
2. **Data, not code.** Packs live in `rule-packs/{cc}/{bookkeeping|tax}/{version}.yaml`.
3. **Never edit a published version.** A change is a new version; the old one gets an
   `effective_to` (exclusive) and later `retired`. Results always record version + content hash.
4. **Ambiguity is an error.** Overlapping rules fail (hit policy `unique`); missing facts never
   match; floats are rejected.

## Lifecycle (blueprint §2.11)

| Step | Status | Who | Gate |
|---|---|---|---|
| 1 Draft content from sources | `draft` | Reviewer (+ local adviser) | Citations on every rule |
| 2 Write tests incl. boundaries | `draft` | Engineer + Reviewer | A test per decision table (`kind`) |
| 3 Content review | `in_review` | Second qualified reviewer (four-eyes for tax layer) | Review comments resolved in the PR |
| 4 Golden-set comparison | `testing` | AI/QA + Reviewer | Pack tests green; golden-set results attached |
| 5 Limited use | `provisional` | Reviewer + Platform Admin | Owner + `review_due` set; **every output goes to human review** |
| 6 Full use | `active` | Reviewer of Record sign-off | Accuracy targets met on real reviewed work |
| 7 Change in law | `under_review` → new version | Reviewer | New version through steps 1–6 |
| 8 End of life | `retired` | Platform Admin | `effective_to` set; kept for history |

## Pull request checklist (copy into the PR)

- [ ] File at its canonical path; `schema_version: 1`
- [ ] Every rule has at least one citation with retrieval date
- [ ] Decimals are quoted strings; no floats
- [ ] Tests cover each `kind`, including boundary values and `no_match` cases
- [ ] `python -m azinco_rules check rule-packs` → `RULE-PACKS-OK`
- [ ] Effective dates do not overlap another usable version
- [ ] Reviewer approval recorded in the PR (name, licence, date); four-eyes for tax layer
- [ ] Change note: what changed in law, and from which date

## Monitoring

`review_due` dates are tracked by the Platform Admin; an overdue pack is moved to
`under_review`. Deadline alert intervals remain GAP-TAX-06.
