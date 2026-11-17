# AZINCO — Project Requirements & Architecture Blueprint
## Part 4 — UI Map

| Field | Value |
|---|---|
| Document | AZINCO Blueprint, Part 4 of 5 |
| Version | 0.1 (DRAFT — awaiting owner approval) |
| Date | 2026-11-17 |
| Sources | Project Instructions (PI) §7, §10; Base Standard (BS) §4.1, §7.5, §10.1, §10.2; Parts 1–3 |
| Scope | Screens, key components and role access for the 14 interfaces of PI §10. Wireframes come later |
| Labels | **[Source]** · **[PI]** · **[Recommended]** |

Role codes: **CO** client owner · **CS** client staff · **OPS** support/ops · **RV** reviewer · **R2** second reviewer · **LP** local partner · **PA** platform admin · **AE** AI engineer · **AU** external auditor · **CMP** compliance officer · **PUB** public.
Phase: P1 = MVP, P2 = automation, P3 = scale (see Part 5).

Global UI rules:
- English + Urdu, RTL-aware [Source BS §7.3(12)].
- Domestic payments are always labelled **"Banking Channels"**; provider names never appear outside the Admin back-office [PI §3].
- "In Escrow (Work Active)" always shows the funds-handling disclosure for Option A [PI §3].
- Money is shown as server-formatted decimal strings with currency; the UI never calculates [PI §5].
- Every AI-produced value shows a confidence badge and an evidence link [PI §5.3].
- Anything mocked or sandboxed carries a visible **[SANDBOX]/[MOCK]** banner in non-prod [PI §13].

---

## 1. Public website & service overview — route group `(public)`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Home | Value proposition ("AI prepares, experts approve"), client segments, CTA | PUB | P1 |
| Services | Bookkeeping, reconciliation, tax records, reports; delivery modes explained per country (no rates) | PUB | P1 |
| How it works | 5-stage journey (BS §4.1) diagram | PUB | P1 |
| Pricing | Pricing models and complexity factors (figures from Admin config — GAP-PAY-01) | PUB | P1 |
| Security & AI disclosure | Human review, data isolation, AI-provider disclosure | PUB | P1 |
| Legal pages | Terms, privacy, refund policy (counsel text) | PUB | P1 |
| Contact | Enquiry form | PUB | P1 |

## 2. Client registration & authentication — `(auth)`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Register | Email, password strength meter, language choice, consent checkboxes | PUB | P1 |
| Verify email | Token handler | PUB | P1 |
| Login | Email/password, MFA prompt, lockout message | all | P1 |
| MFA setup / verify | TOTP QR, recovery codes, step-up modal | all (mandatory for staff) | P1 |
| Forgot / reset password | Token flow | all | P1 |
| Accept invitation | Staff/client-staff invite acceptance | CS, staff | P1 |
| Session & devices | Active sessions, revoke | all | P1 |

## 3. Client onboarding, KYC & business profiles — `(client)/onboarding`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Onboarding wizard | Stepper: business type → jurisdiction → entity details → tax IDs → FYE / currency / method → services | CO, OPS(assist) | P1 |
| KYC upload | Identity & business document upload, status chips | CO | P1 |
| Acceptance status | KYC / sanctions / conflict status, next steps | CO | P1 |
| Jurisdiction notice | "Pack provisional / not available" explanation and expected process | CO | P1 |
| Engagement letter | Letter preview (mode, payment model, funds handling, AI disclosure), e-sign | CO | P1 |
| Opening balances | Upload last statements / TB, import CoA, customers/vendors, asset register | CO, OPS | P1 |
| Business profile | Entities list, profile edit, policies (read-only for client) | CO, CS(read) | P1 |
| Team | Invite client staff, roles, billing visibility grant | CO | P1 |

## 4. Client dashboard — `(client)/dashboard`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Overview | Active tasks with stage tracker, open queries count, amounts due, upcoming deadlines (from pack), recent deliverables | CO, CS | P1 |
| Notifications | Inbox | CO, CS | P1 |
| Preferences | Language, currency display | CO, CS | P1 |

## 5. Task submission & document upload — `(client)/tasks`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| New task | Service picker, period, deadline, notes | CO, CS(draft) | P1 |
| Quote review | Quote lines, model, inclusions, re-quote triggers, accept button | CO | P1 |
| Upload | Drag-and-drop multi-file, progress, virus-scan state, duplicate warnings; completeness checklist side panel | CO, CS | P1 |
| Email-in / mobile camera | Per-task inbound address; camera capture with crop | CO, CS | P2 |
| Change request | Describe extra scope → revised quote | CO | P1 |

## 6. AI processing & task progress tracking — `(client)/tasks/[id]`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Task detail | 5-stage tracker (Onboarding · Task & Advance · AI Processing · Expert Review · Delivery & Settlement), state badge, escrow disclosure, live SSE updates | CO, CS, OPS | P1 |
| Documents tab | Per-document status (scanned, extracted, in review) — no internal confidence shown to client | CO, CS | P1 |
| Queries tab | Questions from reviewer/agents, answer box, attach file | CO, CS | P1 |
| Awaiting info banner | Response deadline, paused clock indicator | CO, CS | P1 |

## 7. Accounting & bookkeeping workspace — `(workspace)`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Entity ledger home | Period selector, period status, close checklist (BS §6.5) | RV, OPS(read) | P1 |
| Chart of accounts | Tree editor, suspense flag, template mapping | RV (edit), OPS(read) | P1 |
| Journals | Grid (draft/posted/reversed), evidence icon per line, reversal action, filters | RV | P1 |
| Journal detail | Lines, evidence links (doc/page/field), rule version, approval record, hash | RV, AU(read) | P1 |
| Trial balance | Code-computed TB, drill-down to journals | RV, CO(approved only) | P1 |
| Bank reconciliation | Statement lines vs ledger, match method, unmatched list with suggested explanations, tolerance meter | RV | P1 |
| Other reconciliations | AR/AP, inventory, tax, payroll | RV | P2 |
| Fixed assets / inventory / payroll journals | Registers, schedules (calculator outputs) | RV | P2 |
| Period close & re-open | Lock (step-up MFA), controlled re-open with reason | RV | P1 |
| Opening balance workbench | Opening TB vs prior statements, differences, adjustment entry | RV | P1 |

## 8. Tax preparation & compliance workspace — `(workspace)/tax`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Tax overview | Delivery mode banner (A–D), pack version & status, provisional warning | RV | P2 |
| Tax computation | Rule-engine results, rule ids, citations panel, working papers | RV | P2 |
| Filing calendar | Deadlines from pack, alert schedule | RV, CO(read) | P2 |
| Tax record pack | Pack builder, preview, approval | RV | P2 |
| Notices & amendments | Notice log as tasks, agent summary, response drafts (Reviewer only) | RV | P3 |
| Mode A filing panel | Hidden unless `filing_enabled` for jurisdiction | RV | Later (gated) |

## 9. Reviewer of Record dashboard — `(review)`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Review queue | Prioritised list (deadline · value · risk), tier chips, filters, assignment, keyboard navigation | RV, R2, LP | P1 |
| Side-by-side review | Left: document viewer with bbox highlight; right: AI output (fields / categorisation / draft journal), confidence badges, one-line reasoning, QA findings, risk flags, rule version + citations | RV, R2 | P1 |
| Action bar | Approve · Edit · Reject & rework · Ask client · Escalate (shortcuts A/E/R/Q/X); step-up MFA for Tier D | RV, R2 | P1 |
| Four-eyes queue | Items awaiting second approval, first-approver info | R2 | P1 |
| Partner co-sign queue | Mode C items | LP | P2 |
| Final statements approval | Statement preview, cross-reference to working papers, approve | RV | P1 |
| Reviewer workload | Queue volume, ageing, delegation | RV, PA | P1 |
| My licence | Licence status, expiry warnings | RV | P1 |

## 10. Platform Admin dashboard — `(admin)`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Portfolio overview | Active clients, international vs local, geography, sector breakdown (BS §10.2) | PA | P1 |
| Clients | Tenant list, acceptance status, engagement terms, kill switch | PA | P1 |
| Engagements | Mode, payment model, funds handling, credit limit | PA | P1 |
| Users & roles | Staff, reviewers, memberships, licence register | PA | P1 |
| Pricing | Price lists, advance %, rush fees (values entered by owner) | PA | P1 |
| Jurisdictions | Allowed modes, `filing_enabled` and `option_b_enabled` toggles with approval workflow | PA + RV | P1 |
| Feature flags & kill switch | Tenant / platform | PA | P1 |

## 11. Billing, payments & Banking Channels management
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Client: Invoices & payments | Invoice list, pay button → choose **Banking Channels** or **Card / PayPal**, receipts, FX shown | CO | P1 |
| Client: Payment status | Pending / succeeded / failed, retry | CO | P1 |
| Admin: Financial matrix | Total revenue, advances received, pending balances, outstanding dues, refunds, gateway fees, FX differences — per client & total, PKR + client currency | PA | P1 |
| Admin: Payment providers (back-office) | Banking Channels providers & international gateways: enable, sandbox flag, secret reference (never the secret), webhook health | PA | P1 |
| Admin: Settlement reconciliation | Daily runs, exceptions, resolve | PA | P1 |
| Admin: Refunds & disputes | Request, approve, record | PA | P1 |

## 12. Financial reports & document downloads — `(client)/downloads`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Download centre | Deliverables list (locked until settlement, with reason), signed-URL download, archive | CO, CS(if granted) | P1 |
| Report viewer | GL, TB, P&L, BS, CF, ageing, bank rec, management summary | CO, RV | P1 (GL/TB/bank rec), P2 (full set) |
| Export & offboarding | Open-format export request, deletion certificate request | CO | P2 |
| Auditor pack | Engagement-scoped audit-support pack, query tracker | AU | P2 |

## 13. Rule-pack & AI agent monitoring dashboard — `(admin)/ai`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Rule-pack manager | Packs per country/layer, versions, status, owner, review due, diff, approvals | PA, RV, AE | P1 |
| Agent operations | Agent status, runs, failures, retries, cost, latency, turnaround | PA, AE | P1 |
| Model registry | Models/prompts per agent & country, release workflow | AE (propose), PA (approve) | P1 |
| Golden-set results | Regression runs, accuracy by doc type/language/country | AE, RV | P1 |
| Threshold & calibration manager | Policy at 5 levels, calibration reports, proposals, shadow-test results, approve/rollback, history | RV, PA, AE | P2 |
| Confidence distribution | Histograms by agent/doc type, tier mix | AE, RV | P2 |

## 14. Audit trail & compliance management — `(admin)/audit`
| Screen | Key components | Roles | Phase |
|---|---|---|---|
| Audit explorer | Event search (actor, action, resource, time), hash-chain verification status | CMP, PA, RV, AU(scoped) | P1 |
| Figure trace | Any report line → journal → extraction field → document page → rule → approver | RV, CMP, AU(scoped) | P1 basic, P2 full |
| Compliance register | KYC/AML reviews, sanctions hits, licence expiries, pack review due dates, incidents | CMP, PA | P2 |
| Retention & deletion | Retention schedule, deletion jobs, certificates | PA, CMP | P2 |

---

## Shared component library [Recommended]
| Component | Used by |
|---|---|
| `StageTracker` (5 stages + state badge) | 4, 6 |
| `DocumentViewer` (PDF/image, zoom, bbox overlay) | 7, 9, 14 |
| `ConfidenceBadge`, `RiskFlag`, `TierChip` | 7, 9, 13 |
| `EvidenceLink` (doc → page → field) | 7, 9, 12, 14 |
| `MoneyText` (server-formatted, currency, base PKR toggle) | everywhere |
| `JournalGrid` (balanced indicator, status) | 7, 9 |
| `ApprovalBar` (actions + step-up MFA) | 7, 8, 9 |
| `CitationPanel` (rule version + sources) | 8, 9, 13 |
| `EscrowDisclosure` | 6, 11 |
| `PaymentChannelPicker` ("Banking Channels" / "Card / PayPal") | 11 |
| `RoleGuard` (UI defence in depth; API is authority) | all |
| `SandboxBanner` | all non-prod |

---

## Part 4 — Summary of coverage

| # | Interface (PI §10) | Screens | Status |
|---|---|---|---|
| 1 | Public website | 7 | Done |
| 2 | Registration & auth | 7 | Done |
| 3 | Onboarding, KYC, profiles | 8 | Done |
| 4 | Client dashboard | 3 | Done |
| 5 | Task submission & upload | 5 | Done |
| 6 | Progress tracking | 4 | Done |
| 7 | Accounting workspace | 10 | Done |
| 8 | Tax workspace | 6 | Done (P2+) |
| 9 | Reviewer dashboard | 8 | Done |
| 10 | Platform Admin | 7 | Done |
| 11 | Billing & Banking Channels | 6 | Done |
| 12 | Reports & downloads | 4 | Done |
| 13 | Rule-pack & agent monitoring | 6 | Done |
| 14 | Audit & compliance | 4 | Done |
| — | Shared components | 12 | Done |
