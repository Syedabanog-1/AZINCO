# goldens — golden test sets and accepted baselines

Governance: `docs/governance/golden-set-plan.md` (BS §7.4, §8.8, §13). Code:
`services/worker/azinco_worker/goldens`.

| Path | What |
|---|---|
| `sets/<set-id>/<version>/manifest.yaml` | Set metadata: status, data policy, chart of accounts, who labelled and who **reviewed**, hash of `items.jsonl` |
| `sets/<set-id>/<version>/items.jsonl` | One item per line: document, its SHA-256, expected account, fields and flags |
| `baselines/*.json` | Accepted reports; CI fails if a new run is worse (`compare`) |

## First set: `invoices-synthetic/v1` — status **draft**

100 **[MOCK] synthetic** documents for invented PK and GB businesses (70 clean, 20 noisy,
10 adversarial: 4 prompt-injection, 3 totals that do not add up, 3 duplicates). Amounts are computed
in code (Decimal); there are no tax lines or rates (those only come from approved rule packs).
Labels were proposed by the generator and must be confirmed by the Reviewer of Record before the
set becomes `reviewed` (the manifest then records `reviewed_by` and `reviewed_on`). English only —
Urdu documents need real-world style samples (GAP-AGT-02).

The committed baseline `invoices-synthetic-v1.mock.json` is the **[MOCK] provider**, which always
answers "Rent": its 0.25 accuracy measures the plumbing, not a model. No accuracy target applies in
Phase 0; the Phase 1 target (≥ 98% field accuracy on the clean set) needs real extraction agents.

```
python -m azinco_worker.goldens check   goldens/sets/invoices-synthetic/v1
python -m azinco_worker.goldens run     goldens/sets/invoices-synthetic/v1 --out /tmp/report.json
python -m azinco_worker.goldens compare /tmp/report.json goldens/baselines/invoices-synthetic-v1.mock.json
```

Sets are immutable once `published`: changes create `v2`. Never put real client data here without
written authorisation and counsel-approved anonymisation.
