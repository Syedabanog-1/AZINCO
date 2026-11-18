# rule-packs

Governed jurisdiction rule-pack sources: `rule-packs/{cc}/{bookkeeping|tax}/{version}.yaml`
(Base Standard §6.6; ADR-0008; schema in `packages/rule-engine`).

**Empty on purpose.** Content is added only from official, current sources with citations and
effective dates, approved by the Reviewer of Record (GAP-TAX-01..05 in the blueprint).

## Adding a pack (lifecycle, blueprint §2.11)

1. Create the file at its canonical path with `status: draft`. Every rule needs `citations`
   (source title, reference, section, retrieved date). Decimals are quoted strings (`"0.17"`).
2. Add `tests:` for every decision table (`kind`), including boundary cases.
3. `python -m azinco_rules check rule-packs` must print `RULE-PACKS-OK`.
4. Reviewer (+ local adviser) approve the content → `testing`; golden-set comparison → the Reviewer
   and Platform Admin move it to `provisional` (owner and `review_due` required). Provisional output
   always goes to human review. `active` only after accuracy targets are met on real work.
5. A published version is never edited: changes create a new version; the old one gets
   `effective_to` and later `retired`.

The check refuses any gated pack (`testing` and later) with a missing citation, owner, review date,
an untested table or a failing test.
