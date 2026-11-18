# ADR-0009: Money and FX — Decimal everywhere, NUMERIC(20,4), base currency PKR

| Field | Value |
|---|---|
| Status | Accepted (implemented Steps 0.5, 0.9) |
| Date | 2026-11-18 |
| Base Standard | §5.1 (record FX at payment; report in client and platform base currency), §8.1 (code calculates) |
| Owner decision | DEC-12: base PKR; reporting PKR **and** USD |

## Decision
* Python `Decimal` (`azinco_common.money.Money`) and PostgreSQL `NUMERIC(20,4)`; FX rates
  `NUMERIC(20,10)`; currency `CHAR(3)` ISO 4217. Floats are rejected at every boundary (API,
  ledger, rule packs); JSON money is a string.
* Base-currency amount = `round_half_up(amount × rate, 4)`, computed by the service, never sent
  by a caller; the database checks the same formula; a property test proves code = database.
* Functional-currency lines use rate 1. Journals balance in base currency; single-currency
  journals also balance in transaction currency.
* Each entity has a functional currency (default PKR). Reporting currencies: PKR, USD.

## Open
FX rate source per currency (GAP-ACC-04) and display rounding per currency — Reviewer + Admin.
