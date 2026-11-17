# packages/py-common — `azinco-common`

Shared Python primitives used by the API, Ledger Service and workers.

| Module | Purpose |
|---|---|
| `azinco_common.money` | `Money` — exact `Decimal` amounts, `NUMERIC(20,4)` precision, same-currency arithmetic, minor-unit rounding, loss-free allocation. Floats are rejected. |

```bash
pip install -e ".[dev]"
pytest      # includes Hypothesis property tests
mypy
```
