# Phase 0 sign-off record

| Field | Value |
|---|---|
| Base Standard | §15 (exit gate), §8.7 (approvals record name, licence status and time) |
| Rule | Signatures are added by the people themselves (commit or signed PDF stored beside this file). An AI assistant never signs. |

## Items to approve

| Item | Document | Approver role | Name | Licence / registration | Decision | Date |
|---|---|---|---|---|---|---|
| ADR-0001 … ADR-0016 | `docs/adr/` | Owner | | — | | |
| Threat model | `threat-model.md` | Security reviewer | | — | | |
| Security checklist | `phase0-security-checklist.md` | Security reviewer | | — | | |
| Delivery-mode matrix | `delivery-mode-matrix.md` | Reviewer of Record + counsel | | | | |
| Rule-pack SOP | `rule-pack-sop.md` | Reviewer of Record | | | | |
| Golden-set plan | `golden-set-plan.md` | Reviewer of Record | | | | |
| Retention draft | `data-retention-draft.md` | Counsel | | — | | |
| Named Reviewer of Record (DEC-13) | — | Owner | Aun Ali Zaidi, FCMA (named by owner in chat, 2026-11-18) | CIMA (UK) — membership no. `######` (masked); certificate verified by owner 2026-11-18 (evidence held privately) | Named and verified — owner signature pending | 2026-11-18 |

## Owner decisions

| ID | Question | Current value |
|---|---|---|
| DEC-01 | First international market | **UK — confirmed by owner 2026-11-18** |
| DEC-02 | Delivery mode per jurisdiction | Not approved anywhere; Mode A disabled |
| DEC-10 | Hosting provider and region, KMS | Open (ADR-0013) |
| DEC-11 | Auth approach | **FastAPI-native — confirmed by owner 2026-11-18** |
| DEC-13 | Named Reviewer of Record and licence | **Aun Ali Zaidi, FCMA — CIMA (UK)**, named by owner 2026-11-18. Membership no. `######` (masked: the real number is kept outside this public repository). Certificate inspected and verified by the owner on 2026-11-18; evidence held outside the repository. Legal review (GAP-LEG-01) must confirm which delivery modes this credential supports in PK and UK |
