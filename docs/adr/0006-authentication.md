# ADR-0006: Authentication — FastAPI-native sessions with Argon2id and TOTP MFA

| Field | Value |
|---|---|
| Status | Accepted (implemented in Step 0.7) |
| Date | 2026-11-17 |
| Deciders | Owner (DEC-11, option a), Engineer |
| Requirements | FR-IAM-01, FR-IAM-03, FR-IAM-04, FR-IAM-07, NFR-SEC-03 |
| Base Standard | BS §8.7 (approver identity), §12 (RBAC, MFA for staff and Reviewers) |
| Label | [Source] requirement, [Recommended] mechanism |

## Context
Reviewers of Record sign off financial statements and tax records. Every approval must be tied to
a verified human with MFA, and the platform must control licence and role data itself.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. FastAPI-native (chosen) | Full control of MFA policy, licence-aware roles, data residency; no per-user fees | More code to own and test |
| B. Managed IdP (Clerk/Auth0/…) | Faster, hosted MFA UX | Vendor lock-in, cost per user, external data processor, harder licence-aware step-up |

## Decision
* Passwords: Argon2id (argon2-cffi defaults), minimum 12 characters; constant-work verification so
  unknown e-mails and wrong passwords take the same time and return the same message.
* Registration never reveals whether an e-mail exists; accounts start `pending_verification` and are
  activated by a single-use, 24-hour e-mail link (token stored as SHA-256).
* Sessions: random 256-bit token in an `HttpOnly; SameSite=Strict` cookie (`Secure` outside local/CI);
  only its SHA-256 is stored. Idle timeout 60 min, absolute 12 h, revocable (logout).
* CSRF: double-submit token (`azinco_csrf` cookie + `X-CSRF-Token` header) on state-changing requests.
* Lockout: 5 failures → 15 minutes (configurable).
* MFA: TOTP (RFC 6238), secret encrypted with Fernet (`AZINCO_MFA_ENCRYPTION_KEY`). Mandatory for staff,
  support, reviewer roles and platform roles before any other action; sign-off permissions require an
  MFA-verified session (step-up).
* Pre-context lookups (login, session resolve, e-mail verification) use SECURITY DEFINER functions owned
  by `azinco_migrator`, protected by migrator-only RLS policies; the app role can only EXECUTE them.
* Browser → API traffic goes through the web app's same-origin proxy with a path allow-list.

## Consequences
* Positive: no third-party IdP holds client identities; MFA policy matches BS §12 exactly.
* Negative: we own password reset, e-mail delivery, rate limiting and session management.
* Follow-ups: password reset flow; per-IP rate limiting in Redis; WebAuthn/passkeys; licence register
  for Reviewers (FR-IAM-06); audit events for every auth action (Step 0.8).

## Validation
`tests/test_auth_units.py` and `tests/test_auth_flow.py` (register, verify, login, lockout, CSRF,
MFA enrolment and login, staff MFA enforcement, RBAC + RLS tenant access).
