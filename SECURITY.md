# Security Policy — AZINCO

AZINCO handles financial and personal data. Status: **pre-alpha, not production-ready.**

## Secrets
- Secrets live only in `.env` (git-ignored) or a secrets manager. `.env.example` contains placeholders only.
- `gitleaks` and `detect-private-key` run on every commit and in CI.
- If a secret is ever committed or pasted anywhere public: **revoke/rotate it immediately**, then remove it from history.

## Data
- Development and tests use synthetic data only.
- Card data is never stored; only PCI-compliant hosted payment pages are used.

## Reporting a vulnerability
Report privately to the repository owner (do not open a public issue). Include steps to reproduce, impact and affected component.

## Baseline controls (Base Standard §12)
Tenant isolation (RLS + per-tenant keys), TLS in transit, AES-256 at rest, RBAC + MFA for staff and Reviewers, immutable audit log, signed + idempotent payment webhooks, virus-scanned uploads, signed time-limited download URLs, PII masking in logs and prompts, prompt-injection defences, tested backups.
