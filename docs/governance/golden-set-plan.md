# Golden-set programme plan

| Field | Value |
|---|---|
| Base Standard | §7.4 (calibration, N_min, cold start), §8.8 (first release: every item to the Reviewer; autonomy only after golden-set and calibration results), §13 (accuracy KPIs), §15 (exit gates) |
| Gap | GAP-AGT-02 — no sample documents exist; sets must be synthetic or properly anonymised |
| Owner | Reviewer of Record (truth labels) · AI/QA engineer (harness, metrics) |
| Phase 0 criterion | The golden-set **framework** and a first synthetic set exist — no accuracy target yet |

## What a golden set is

A versioned collection of documents with **reviewer-approved expected outputs** (fields, categories,
journal proposals, matches, tax codes) used to measure every model, prompt, OCR engine and rule-pack
change before it can be used — and at every phase exit gate.

## Data rules

1. **Synthetic first.** Generated documents for invented businesses (jurisdiction tags PK, GB, …;
   the rule-engine tests use `ZZ` for non-country fixtures). No real client data without written
   authorisation and anonymisation reviewed by counsel (GAP-LEG-03).
2. Each item: `id`, document (file + hash), `doc_type`, `language` (EN; Urdu where available),
   `jurisdiction`, `business_type`, `difficulty` (clean / noisy / adversarial), expected outputs,
   labeller, reviewer, label date, set version.
3. **Adversarial items are mandatory**: prompt-injection text inside documents, duplicates,
   wrong currency, totals that do not add up, unreadable scans.
4. Sets are immutable once published (new version for changes); stored with access limited to
   the QA role; results are kept with model id, prompt version, rule-pack version and content hash.

## Coverage plan (Phase 1 MVP: PK + first international market, DEC-01)

| Area | Doc types | Initial size target | Measures |
|---|---|---|---|
| Extraction | purchase/sales invoices, receipts, bank statements, utility bills | ≥ N_min per doc type before any autonomy (BS §7.4; default N_min 200, DEC-05) | field accuracy, missing-field rate |
| Categorisation | the above → chart of accounts | same | override rate, top-1 accuracy, calibration gap |
| Reconciliation | statement lines ↔ ledger | synthetic month per business type | auto-match rate, false-match rate, unreconciled value |
| Tax coding | only after a pack is `testing` (GAP-TAX-01/02) | per pack | rule-citation coverage, exact match |
| Safety | adversarial set | all agents | injection success rate (target 0), schema violations |

## Targets and gates

* Phase 1 exit: extraction field accuracy **≥ 98%** on the clean synthetic set [BS §13, roadmap
  Phase 1 criteria]; 100% of journal lines carry evidence links; Reviewer sign-off on a full pilot.
* Confidence tiers and any autonomy stay **off** until calibration on the golden set justifies
  them; loosening a threshold needs Reviewer approval; Tier D is never automated [BS §7.4, §8.8].
* Defaults T_auto 98%, T_floor 95%, Tier B sample 20%, Tier A audit 5% apply only until calibrated
  (DEC-05) and remain Reviewer decisions.

## Harness (Phase 1 build)

`goldens/` versioned sets → runner calls the same Model Gateway and graphs with the [MOCK] or a
real provider → scores per measure → report stored with all version identifiers → CI job compares
against the last accepted report and fails on regression.

## Phase 0 status

Done: framework `services/worker/azinco_worker/goldens` (schema with document hashes, deterministic
[MOCK] generator, scorers for categorisation / fields / injection resistance / flags, runner,
regression gate, CLI) and the first set `goldens/sets/invoices-synthetic/v1` (100 synthetic items,
status **draft**) with a [MOCK] baseline. CI checks set integrity and fails on any regression.
Open: Reviewer of Record confirms the labels (→ `reviewed`); Urdu items; extraction predictor and
real-provider runs arrive with the Phase 1 agents.
