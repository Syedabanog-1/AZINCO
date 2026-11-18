# packages/rule-engine — `azinco_rules`

Versioned jurisdiction rule packs and a **pure** decision-table evaluator (Base Standard §6.6, §8.2;
ADR-0008). No tax rate, threshold or deadline lives in code — only in governed, cited packs under
`rule-packs/`, which stay **empty until sourced content is approved** (GAP-TAX-01..05).

```python
from datetime import date
from pathlib import Path
from azinco_rules import Layer, Registry, evaluate

registry = Registry.load_dir(Path("rule-packs"))
pack = registry.select("PK", Layer.TAX, date(2026, 9, 30))   # NoPackError until a pack exists
result = evaluate(pack, "tax_rate", {"supply_type": "standard", "registered": True})
result.outputs, result.rule_ids, result.citations, result.version, result.content_hash
result.needs_human_review   # True unless the pack is `active` (provisional => Reviewer, §6.6)
```

| Rule | How |
|---|---|
| Pure & deterministic | `evaluate()` has no I/O and no clock; property tests prove same input → same output and that rule order does not matter |
| No silent guesses | Hit policy `unique` (default): two matching rules raise `AmbiguousRuleError`; a missing fact never matches |
| No floats | Decimals are quoted strings in YAML (`"0.17"`); a float anywhere is rejected |
| Effective dating | `select()` picks the version with `effective_from ≤ date < effective_to`; two usable versions may not overlap |
| Traceability | Every result carries rule ids, citations, version and a `content_hash` of the whole pack |
| Activation gate | `testing/provisional/active/under_review` packs need ≥ 1 rule, a citation on **every** rule, owner, review date, a test per decision table, and **all pack tests passing** |
| Canonical path | `rule-packs/{cc}/{bookkeeping\|tax}/{version}.yaml` |

CLI (used by CI and the `api-test` container):

```
python -m azinco_rules check rule-packs      # RULE-PACKS-OK (n pack(s); ...) / exit 1 on any problem
```

Tests use a **[MOCK]** synthetic pack for jurisdiction `ZZ` (an ISO user-assigned code that belongs
to no country): `tests/fixtures/zz/tax/2026.1.yaml`. Its values are invented and must never be used.
