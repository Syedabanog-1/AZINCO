# Contributing to AZINCO

## Branches and commits
- `main` is protected. Work on branches: `feat/<area>-<short>`, `fix/<area>-<short>`, `chore/...`, `docs/...`.
- Conventional Commits: `feat(api): add tenant RLS dependency`, `fix(ledger): reject unbalanced draft`.
- One Phase 0 step per pull request where possible.

## Every pull request must
1. Pass `pre-commit run --all-files` and CI.
2. Reference requirement IDs (e.g. `FR-LED-03`, `NFR-SEC-01`) and Base Standard sections (e.g. `BS §8.4`).
3. Include tests: unit; property-based for ledger, money, tax, FX; integration for DB/RLS.
4. Change the database only through Alembic migrations.
5. Use `Decimal` / `NUMERIC(20,4)` for money — never `float`.
6. Label anything mocked or sandbox-only as **[MOCK]** / **[SANDBOX]** in code and docs.
7. Never add tax rates, deadlines or thresholds without a rule-pack source citation approved by the Reviewer of Record.
8. Never name domestic payment providers in client-facing code or text — use **Banking Channels**.

## Architecture decisions
Significant choices are recorded as ADRs in `docs/adr/` using `0000-template.md`.

## Data
Only synthetic data in development and tests. Real client data requires written authorisation and never enters this repository.
