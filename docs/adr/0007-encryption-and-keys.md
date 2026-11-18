# ADR-0007: Encryption and keys

| Field | Value |
|---|---|
| Status | Accepted for Phase 0 scope; envelope encryption Proposed for Phase 1 |
| Date | 2026-11-18 |
| Base Standard | §12 (encryption in transit and at rest, secrets handling) |
| Label | [Source] requirement, [Recommended] mechanisms |

## In place (Phase 0)
* Passwords: Argon2id. Session and verification tokens stored only as SHA-256 hashes.
* MFA secrets: Fernet-encrypted with `AZINCO_MFA_ENCRYPTION_KEY`; startup refuses a missing key
  outside local/CI.
* Secrets only in `.env` (git-ignored) generated per machine/CI run; gitleaks in CI.
* Service tokens for the Ledger Service (ADR-0016); DB password per role.

## Proposed (Phase 1, before real client data)
* TLS everywhere outside the local Docker network; HSTS on the web edge.
* Envelope encryption: per-tenant data-encryption key wrapped by a KMS/Vault master key; object
  storage server-side encryption with per-tenant keys; encrypted backups with tested restore
  (RTO 4h / RPO 15m, BS §13 indicative).
* Key rotation runbook (MFA key re-encryption job, service-token rotation).
* KMS choice depends on hosting (ADR-0013, DEC-10).
