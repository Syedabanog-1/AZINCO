# ADR-0011: Payment adapter — provider-agnostic, "Banking Channels" and card via Stripe

| Field | Value |
|---|---|
| Status | Proposed (implemented in Phase 1 with [MOCK] and [SANDBOX] providers first) |
| Date | 2026-11-18 |
| Base Standard | §5.1 (advance/balance, FX recorded), §5.2 (gateways; idempotent, signature-verified webhooks; daily reconciliation), §5.3 (escrow wording, Options A/B), §4.3 (payment-gated states) |
| Owner decision | DEC-14: international payments via **Stripe** only (PayPal removed); client label "Card", "processed by Stripe" |

## Decision (proposed)
* One `PaymentProvider` interface: create payment intent, verify webhook signature, parse event,
  fetch settlement report. Providers: `mock`, `stripe` (sandbox first), and domestic providers
  configured by the Platform Admin in back-office settings only.
* Client-facing name for all domestic options is **Banking Channels**; provider names never appear
  in client screens, documents, invoices, emails or API docs.
* Webhooks: signature verified, idempotent by event id, stored raw + parsed, audited; daily
  reconciliation against settlement reports; mismatches go to an exceptions queue.
* FX rate recorded at payment time; amounts reported in client currency and PKR (ADR-0009).
* `funds_handling = ledger | segregated` per tenant/jurisdiction/service. **Option A (ledger) is the
  default**; "In Escrow (Work Active)" is only a task status and is never described as legally
  segregated escrow. Option B stays disabled until the Reviewer of Record and counsel approve it
  for that country (GAP-LEG-02).
* No agent can move money; payment actions need a human (project principle).

## Open
GAP-PAY-01…05 (prices, refunds, retainers, credit limits, Banking Channels providers and their
settlement formats). PayPal can be re-added later as another provider behind the same interface.
