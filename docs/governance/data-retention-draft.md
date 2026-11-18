# Data retention and deletion — draft

| Field | Value |
|---|---|
| Base Standard | §12 (retention and deletion controls), §4 (offboarding and archive) |
| Status | Draft. **All legal periods are open** — GAP-LEG-05 (retention per jurisdiction), GAP-LEG-03 (privacy obligations). No period below is decided |

| Data class | Where | Default handling until counsel decides |
|---|---|---|
| Posted ledger, approvals, audit trail | `ledger`, `app.approvals`, `audit` | Never deleted by the application (immutable by design); legal period: GAP-LEG-05 |
| Client source documents | object storage (tenant-scoped keys) | Kept for the engagement; legal period: GAP-LEG-05 |
| Agent checkpoints | `agent_state` | Not yet purged; [Recommended] purge completed threads after the task is archived |
| Sessions, verification tokens | `app.sessions`, `app.email_verification_tokens` | Expire; [Recommended] periodic purge of expired rows |
| Logs | container logs | Masked; local dev rotates by Docker defaults |
| Golden sets | QA storage | Synthetic; no personal data |

Deletion requests are recorded in the audit log; financial records that the law requires to keep
are retained and access-restricted rather than deleted. Every period must be confirmed by counsel
for each jurisdiction before Phase 1 go-live.
