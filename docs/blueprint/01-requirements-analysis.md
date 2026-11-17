# AZINCO — Project Requirements & Architecture Blueprint
## Part 1 — Requirements Analysis

| Field | Value |
|---|---|
| Document | AZINCO Blueprint, Part 1 of 5 |
| Version | 0.2 (DRAFT — awaiting owner approval; DEC-12 resolved: base currency PKR) |
| Date | 2026-11-17 |
| Primary source | `Global_Accounting_AI_Agency.pdf` — Base Standard (33 pp), cited as "BS §x" |
| Supporting source | `Platform_Base_Standard_Summary.pdf` (1 p) — no conflicts with the Base Standard found |
| Customisation | AZINCO Project Instructions v2 (cited as "PI §x") — "Banking Channels" replaces domestic provider names |
| Labels | **[Source]** = stated in the Base Standard. **[Recommended]** = AZINCO enhancement, not in the Base Standard. **[PI]** = mandated by AZINCO Project Instructions |

> Status: This is a requirements document, not a statement of production readiness. No tax rate, deadline, threshold or regulation is stated here unless the Base Standard states it; everything else is listed as a gap in §1.13.

---

## 1.1 Project overview and business objectives

**One-sentence definition [Source, BS §1]:** a client (Pakistani or international) submits a task with financial documents and pays an advance; AI agents ingest, categorise, reconcile and prepare the books and tax records; a Chartered Accountant / Financial Expert (the Reviewer of Record) reviews and approves; the client pays the balance and receives audit-ready deliverables.

**Core rule [Source, BS §2, §8.1]:** *AI prepares → deterministic code calculates → qualified human approves → client receives deliverables.*

### Business objectives

| ID | Objective | Label |
|---|---|---|
| BO-01 | Serve Pakistani and international clients (shops/retail, factories, malls/property, corporates, SMEs, individuals) from any country | [Source] BS §1 |
| BO-02 | Deliver bookkeeping/GL, tax-record preparation, financial statements and management reporting | [Source] BS §1 |
| BO-03 | Automate preparation with a multi-agent AI system while keeping a qualified human accountable for every sign-off | [Source] BS §2.1 |
| BO-04 | Treat jurisdictions as configuration (rule packs), so new countries are onboarded without code changes | [Source] BS §2.4, §6.6 |
| BO-05 | Grow autonomy only as measured accuracy earns it (calibrated confidence tiers) | [Source] BS §2.10, §7.4 |
| BO-06 | Use Karachi (PKT, UTC+5) time-zone advantage: overnight AI processing for North America, next-morning results | [Source] BS §3.4 |
| BO-07 | Protect cash flow: no work without commitment, deliverables only after payment | [Source] BS §2.3, §5.1 |
| BO-08 | Present one business-facing payment term, "Banking Channels", for domestic Pakistani payments | [PI] PI §3 |
| BO-09 | Be commercially viable: measurable straight-through rate, human minutes/document, AI cost/task, gross margin/client | [Source] BS §7.8, §13 |

### Scope

- **In scope [Source, BS §1, PI §4]:** GL & double-entry bookkeeping; AP/AR; bank & cash reconciliation; inventory and fixed assets; payroll accounting records; financial statements & management reports; tax computation & compliance preparation (sales tax/VAT/GST, income tax, withholding, payroll tax records); multi-currency & multi-jurisdiction; onboarding, KYC/AML, engagement letters, billing, delivery, offboarding, archive.
- **Out of scope (until enabled):** tax filing (Mode A) per jurisdiction until licensing, legal authority and human approval are verified and recorded [PI §8, BS §3.3]; legally segregated client funds (Option B) until approved [BS §5.3]; card-data storage (never — PCI gateways only) [BS §12].

---

## 1.2 Functional requirements (by module)

ID format: `FR-<MODULE>-<nn>`. These IDs are used in the Traceability Matrix (§1.12).

### M1 — Identity, Tenancy & Access (IAM)
| ID | Requirement | Label |
|---|---|---|
| FR-IAM-01 | Client self-registration with email verification | [Source] BS §10.1 |
| FR-IAM-02 | Each client organisation is a tenant with an isolated, encrypted "tenant vault" created at onboarding | [Source] BS §4.1, §17 |
| FR-IAM-03 | Role-based access control per §1.4 matrix | [Source] BS §12 |
| FR-IAM-04 | MFA mandatory for Reviewers, Admins, Support/Ops staff and Engineers; optional-but-encouraged for clients | [Source] BS §12; client MFA [Recommended] |
| FR-IAM-05 | Client owner can invite client staff with restricted roles | [Recommended] |
| FR-IAM-06 | Reviewer profile stores licence(s): body, number reference, jurisdiction(s), status, expiry, verification evidence | [Source] BS §8.7, §9.6 |
| FR-IAM-07 | Session management, password policy, account lockout, device/session revocation | [Recommended] |
| FR-IAM-08 | Language (English, Urdu minimum) and currency preferences per user | [Source] BS §10.1, §7.3(12) |

### M2 — Client Onboarding, KYC/AML & Engagement (ONB)
| ID | Requirement | Label |
|---|---|---|
| FR-ONB-01 | Capture business type (Shop, Mall, Factory, Corporate, Other), home jurisdiction, entity type, size, activities | [Source] BS §4.1, §6.6 |
| FR-ONB-02 | Capture tax registration numbers, fiscal year end, base currency, accounting method (cash/accrual), framework | [Source] BS §4.2(1), §6.1 |
| FR-ONB-03 | Assign jurisdiction rule pack, CoA template (+ industry extension) and currency settings | [Source] BS §4.1, §6.2 |
| FR-ONB-04 | If no Active pack exists, start Jurisdiction Onboarding Protocol (client is not refused) | [Source] BS §3.3, §6.6 |
| FR-ONB-05 | Client acceptance: identity & business verification, sanctions and PEP screening, delivery-mode availability check | [Source] BS §9.6 |
| FR-ONB-06 | Conflict-of-interest and independence check before acceptance | [Source] BS §9.6 |
| FR-ONB-07 | Delivery mode (A–D) chosen at onboarding, shown on the quote, written into the contract | [Source] BS §3.3 |
| FR-ONB-08 | Engagement letter generated from template with all BS §9.1 clauses (scope, period, deliverables, mode, client duties, AI disclosure & consent, fees, payment model, refund/dispute, turnaround, revision allowance, liability, confidentiality, data processing, governing law, termination, data return/retention) and e-signed before work | [Source] BS §9.1 |
| FR-ONB-09 | Payment model (Advance+Balance / Pay-on-completion / Retainer) set by Platform Admin and written into the letter | [Source] BS §9.3 |
| FR-ONB-10 | `funds_handling = ledger | segregated` stored per tenant / jurisdiction / service and shown to client before payment | [Source] BS §5.1, §5.3 |
| FR-ONB-11 | Opening balances: opening TB agreed to last signed statements/returns/prior accountant; differences posted to documented opening-balance adjustment; Reviewer approval | [Source] BS §6.9 |
| FR-ONB-12 | Import existing CoA, customer/vendor lists, fixed-asset register, inventory and loan schedules, mapped to template | [Source] BS §6.9 |
| FR-ONB-13 | Record cut-over date; lock and mark migrated periods | [Source] BS §6.9 |
| FR-ONB-14 | Catch-up of prior periods as separate scoped task with its own quote | [Source] BS §6.9 |
| FR-ONB-15 | Agree close calendar (month-end / year-end) at onboarding | [Source] BS §6.11 |
| FR-ONB-16 | Record tenant accounting policies: inventory costing (FIFO/weighted avg), capitalisation threshold, depreciation per asset class, FX rate source & revaluation rule, revenue recognition per business type | [Source] BS §6.10 |

### M3 — Task, Scope & Quote (TSK)
| ID | Requirement | Label |
|---|---|---|
| FR-TSK-01 | Create task with services (bookkeeping, reconciliation, sales-tax/VAT/GST records, income-tax records, payroll records, reports), period, deadlines | [Source] BS §4.2(2) |
| FR-TSK-02 | Show completeness checklist per service type at upload | [Source] BS §9.5 |
| FR-TSK-03 | Quote states pricing model, inclusions, complexity factors, and re-quote triggers | [Source] BS §9.2 |
| FR-TSK-04 | Task state machine enforced exactly as §1.8.1 | [Source] BS §4.3 |
| FR-TSK-05 | Change request + revised quote for out-of-scope work; extra scope starts only after acceptance | [Source] BS §9.4 |
| FR-TSK-06 | "Awaiting Client Info" pauses turnaround clock after response period; reminders sent | [Source] BS §9.5 |
| FR-TSK-07 | Real-time progress tracker across the 5 stages visible to client throughout | [Source] BS §4.1, §10.1 |
| FR-TSK-08 | Rework classified as client-caused (chargeable) or platform-caused (not chargeable) | [Source] BS §9.4 |

### M4 — Document Intake & Storage (DOC)
| ID | Requirement | Label |
|---|---|---|
| FR-DOC-01 | Upload by drag-and-drop, email-in, mobile camera | [Source] BS §10.1 |
| FR-DOC-02 | Virus scan every upload before any processing | [Source] BS §4.2(4) |
| FR-DOC-03 | De-duplicate by file hash (and later by content) | [Source] BS §4.2(4), §6.4(2) |
| FR-DOC-04 | Classify document type (BS §6.3 list: sales/purchase invoices, receipts, credit/debit notes, bank & card statements, cash books, payroll sheets, utility bills, customs/import docs, tax challans & returns, loan statements, fixed-asset invoices, stock sheets) | [Source] BS §6.3 |
| FR-DOC-05 | Store encrypted, tenant-scoped object keys | [Source] BS §4.2(4), §12 |
| FR-DOC-06 | Download only via signed, time-limited URLs | [PI] PI §11 |
| FR-DOC-07 | Any language / currency format accepted | [Source] BS §6.3 |

### M5 — Extraction & Validation (EXT)
| ID | Requirement | Label |
|---|---|---|
| FR-EXT-01 | OCR + vision extraction to structured JSON (vendor, number, date, currency, lines, tax, totals) | [Source] BS §7.3(3) |
| FR-EXT-02 | Per-field confidence and link to the source region (document, page, bounding box) | [Source] BS §7.3(3), PI §5.3 |
| FR-EXT-03 | De-skew/enhance, table extraction, handwriting, multi-page statements | [Source] BS §7.3(3) |
| FR-EXT-04 | Validation: arithmetic (re-computed in code), date & period, currency, duplicates (hash + fuzzy on vendor/number/date/amount), vendor/customer matching | [Source] BS §4.2(6), §6.4(2), §7.3(4) |
| FR-EXT-05 | OCR failure → route to human manual entry; case added to golden set | [Source] BS §8.5 |

### M6 — Ledger & Bookkeeping (LED)
| ID | Requirement | Label |
|---|---|---|
| FR-LED-01 | Tenant CoA from template ranges 1000–8000 + industry extensions | [Source] BS §6.2 |
| FR-LED-02 | Categorisation: tenant rules & vendor history first, model only for the rest; one-line reason per decision | [Source] BS §8.1, §7.3(5) |
| FR-LED-03 | Journal drafts are double-entry; DR = CR enforced by ledger service **and** database | [Source] BS §8.4 |
| FR-LED-04 | Posted entries immutable; corrections only by reversal linked to original + re-post | [Source] BS §6.4(6), §8.4 |
| FR-LED-05 | Every journal line links to document, extraction, rule version and approver/auto-approval rule | [Source] BS §6.4(1), §8.4 |
| FR-LED-06 | Unsupported entries go to suspense account and are flagged; never silently categorised | [Source] BS §6.4(5) |
| FR-LED-07 | Tax separated from net at posting (input/output tax, withholding) — computed by rule engine | [Source] BS §6.4(4) |
| FR-LED-08 | Foreign currency at transaction-date rate; period-end revaluation (deterministic) | [Source] BS §6.4(3) |
| FR-LED-09 | Period lock; closed periods reject posting except via controlled re-opening approved by Reviewer and logged | [Source] BS §6.5, §6.11, §8.4 |
| FR-LED-10 | Accruals, prepayments, depreciation schedules — computed in code | [Source] BS §7.3(6), §8.1 |
| FR-LED-11 | Inventory (costing method, stock counts, write-downs approved by Reviewer); fixed assets (register, depreciation, disposals reviewed); payroll journals from payroll records with restricted access | [Source] BS §6.10 |
| FR-LED-12 | Related-party and owner transactions always Tier D | [Source] BS §6.10 |
| FR-LED-13 | Estimates and provisions proposed by agent with basis stated; decided by Reviewer | [Source] BS §6.10 |
| FR-LED-14 | Multi-entity / inter-company balances and consolidation for corporates | [Source] BS §6.2 |
| FR-LED-15 | Hash-chained ledger audit | [Source] BS §8.2 |

### M7 — Reconciliation & Close (REC)
| ID | Requirement | Label |
|---|---|---|
| FR-REC-01 | Bank/card reconciliation: exact → rules → fuzzy matching; unmatched list with suggested explanations | [Source] BS §7.3(7) |
| FR-REC-02 | AR/AP to sub-ledgers and confirmations; inventory to stock records; fixed assets roll-forward; tax accounts to returns & challans; payroll to payroll records | [Source] BS §6.5 |
| FR-REC-03 | Tolerance per tenant; differences above tolerance escalate | [Source] BS §7.3(7) |
| FR-REC-04 | Close checklist (BS §6.5) incl. TB balanced, suspense cleared/explained, period locked after approval | [Source] BS §6.5 |
| FR-REC-05 | Year-end: accrual/provision review, stock & asset verification, statutory statements in pack format | [Source] BS §6.11 |
| FR-REC-06 | Audit-support pack (TB, ledgers, reconciliations, working papers, audit trail); auditor queries tracked as tasks | [Source] BS §6.11 |

### M8 — Tax & Compliance (TAX)
| ID | Requirement | Label |
|---|---|---|
| FR-TAX-01 | Two-layer Jurisdiction Rule Pack (Layer 1 bookkeeping/reporting, Layer 2 tax) versioned with effective dates and source citations | [Source] BS §6.6 |
| FR-TAX-02 | Pack status Active / Provisional / Not available; status limits autonomy | [Source] BS §6.6 |
| FR-TAX-03 | Jurisdiction Onboarding Protocol 7 steps (Capture → Draft → Review → Delivery mode → Test → Activate Provisional → Promote & maintain) | [Source] BS §6.6 |
| FR-TAX-04 | Pack re-review ≥ every 6 months, at start of each tax year, and on law-change alert | [Source] BS §6.6 |
| FR-TAX-05 | Rule engine computes sales tax/VAT/GST, withholding, income-tax provision from pack — never from model memory | [Source] BS §6.6, §7.3(8), §8.1 |
| FR-TAX-06 | Filing calendar and deadline alerts at defined intervals, escalating to Reviewer and client | [Source] BS §6.12, §7.3(8) |
| FR-TAX-07 | Tax record pack with working papers and exact rule-pack version + citations | [Source] BS §6.7, PI §7 |
| FR-TAX-08 | Multi-country tenant: home pack governs books; other packs govern tax arising there; cross-border items always to Reviewer | [Source] BS §6.6 |
| FR-TAX-09 | Tax notices logged as tasks, summarised by agents, answered only via Reviewer within delivery mode | [Source] BS §6.12 |
| FR-TAX-10 | Amended returns follow reversal-and-repost, Reviewer approval | [Source] BS §6.12 |
| FR-TAX-11 | Mode A (filing) feature-flag **disabled** per jurisdiction until licensing, legal authority and human approval recorded | [PI] PI §8; [Source] BS §3.3 |

### M9 — Review & Approval (REV)
| ID | Requirement | Label |
|---|---|---|
| FR-REV-01 | Review queue prioritised by deadline, value and risk, with assignment, due time, pool & delegation | [Source] BS §8.2, §8.7 |
| FR-REV-02 | Side-by-side viewer: source document (highlighted region) + AI output, confidence, reasoning, QA and risk findings | [Source] BS §7.5, §10.2 |
| FR-REV-03 | Actions: approve, edit, reject & rework, ask client, escalate; keyboard shortcuts | [Source] BS §7.5, §8.7 |
| FR-REV-04 | Every approval records reviewer name, licence status, timestamp; **never** by an agent | [Source] BS §8.7 |
| FR-REV-05 | Four-eyes: second qualified reviewer for high-value / high-risk engagements before release | [Source] BS §8.7 |
| FR-REV-06 | Every human correction stored as labelled feedback (evaluation + tenant-level rules) | [Source] BS §7.5 |
| FR-REV-07 | Release 1: **every** item goes to Reviewer; Tiers A/B disabled | [Source] BS §8.8 |
| FR-REV-08 | Tier D always human: tax filings, final statements, related-party/unusual, period close, client sign-off, Provisional-pack outputs | [Source] BS §7.4 |

### M10 — Reporting & Delivery (RPT)
| ID | Requirement | Label |
|---|---|---|
| FR-RPT-01 | GL & TB; P&L; Balance Sheet; Cash Flow; AR/AP ageing; bank reconciliation statements; tax computation & tax-ready pack; management summary (ratios, flagged risks); audit trail on request | [Source] BS §6.7 |
| FR-RPT-02 | Statement formats from Layer 1 pack; cross-referenced to working papers | [Source] BS §6.6, §7.3(9) |
| FR-RPT-03 | Figures in reports come only from ledger/rule-engine; LLM text only for commentary | [Source] BS §2.9 |
| FR-RPT-04 | Final deliverables locked until settlement; progress views visible throughout | [Source] BS §5.1 |
| FR-RPT-05 | Download centre; open-format export (e.g., CSV/XLSX/PDF) at offboarding | [Source] BS §9.7, §10.1 |

### M11 — Billing, Payments & Banking Channels (PAY)
| ID | Requirement | Label |
|---|---|---|
| FR-PAY-01 | Provider-agnostic payment adapter; domestic Pakistan payments shown only as **"Banking Channels"** | [PI] PI §3 |
| FR-PAY-02 | Specific domestic providers configured by Platform Admin in back-office only; never named client-facing | [PI] PI §3 |
| FR-PAY-03 | International gateways (Stripe, PayPal) configurable behind same adapter | [Source] BS §5.2 |
| FR-PAY-04 | Webhooks idempotent, signature-verified; daily reconciliation against settlement reports | [Source] BS §5.2 |
| FR-PAY-05 | FX rate recorded at each payment; reports in client currency and platform base currency | [Source] BS §5.1 |
| FR-PAY-06 | Advance %, currency, refund terms configurable per service and client segment | [Source] BS §5.1 |
| FR-PAY-07 | Three payment models (§1.8.2) incl. pay-on-completion controls (approved clients, credit limit, revert after late payment) | [Source] BS §9.3 |
| FR-PAY-08 | Funds handling Option A/B (§1.8.3); Option B disabled until Reviewer + counsel approval | [Source] BS §5.3 |
| FR-PAY-09 | Invoices, quotes, receipts; overdue flags | [Source] BS §7.3(13) |
| FR-PAY-10 | Agency financial matrix per client and total: Total Revenue, Advances Received, Pending Balances, Outstanding Dues, refunds, gateway fees, FX differences | [Source] BS §5.4 |
| FR-PAY-11 | Card data never stored — PCI gateway handles it | [Source] BS §12 |
| FR-PAY-12 | Refund & dispute workflow per policy | [Source] BS §4.3 |
| FR-PAY-13 | No agent can move money or change prices | [Source] BS §7.7 |

### M12 — Communication (COM)
| ID | Requirement | Label |
|---|---|---|
| FR-COM-01 | Secure chat & query inbox per task | [Source] BS §10.1 |
| FR-COM-02 | Agent-drafted updates/queries; English & Urdu minimum | [Source] BS §7.3(12) |
| FR-COM-03 | Messages with legal, tax-advice or pricing effect are drafts for human approval — never autonomous | [Source] BS §7.3(12), §8.1 |
| FR-COM-04 | Email/notification templates with policy checks | [Source] BS §8.1 |

### M13 — Agent Platform (AGT)
| ID | Requirement | Label |
|---|---|---|
| FR-AGT-01 | Supervisor-led state graph: order, parallel branches, retries, checkpoints, human interrupts, resume | [Source] BS §7.1, §8.2 |
| FR-AGT-02 | Model gateway: routing, failover, caching, budget caps, PII masking, logging, version pinning | [Source] BS §8.2 |
| FR-AGT-03 | Step contract: typed I/O schemas, idempotency key, timeout/retry/cost cap, checkpoint, least privilege, full trace | [Source] BS §8.3 |
| FR-AGT-04 | Confidence policy (T_auto, T_floor, V_max, sample/audit rates, N_min) at 5 levels; most specific wins; guardrail minimum | [Source] BS §7.4 |
| FR-AGT-05 | Calibration engine 7 steps + cold start + auto-tighten; loosening needs Reviewer approval; Tier D never loosened | [Source] BS §7.4 |
| FR-AGT-06 | Model registry: model, version, prompt, rule pack per agent and country | [Source] BS §8.6 |
| FR-AGT-07 | Golden test set per jurisdiction & business type; regression + shadow test before every release | [Source] BS §7.8, §8.6 |
| FR-AGT-08 | Kill switch per tenant and platform; loop & cost limits | [Source] BS §7.7, §8.5 |
| FR-AGT-09 | Tools exposed narrowly (MCP servers or internal APIs) with own permissions | [Source] BS §8.2 |

### M14 — Audit, Admin & Governance (ADM)
| ID | Requirement | Label |
|---|---|---|
| FR-ADM-01 | Immutable, append-only audit log of all agent and human actions (inputs, prompts, model/version, tool calls, outputs, confidence, edits, approvals, timestamps, identity) | [Source] BS §7.3(15), §12 |
| FR-ADM-02 | Audit explorer: trace any figure → source, rule, approver | [Source] BS §10.2 |
| FR-ADM-03 | Portfolio overview (active clients, international vs local, geography, sector) | [Source] BS §10.2 |
| FR-ADM-04 | Rule-pack manager (versions, effective dates, status, approval, per country) | [Source] BS §10.2 |
| FR-ADM-05 | Threshold & calibration manager (policy at every level, reports, proposals, history) | [Source] BS §10.2 |
| FR-ADM-06 | Agent operations view (status, confidence distribution, failures, cost, turnaround) | [Source] BS §10.2 |
| FR-ADM-07 | Change control: prompts, models, thresholds, packs versioned, tested, approved, logged | [Source] BS §16 |
| FR-ADM-08 | Pricing configuration and payment-provider configuration (Banking Channels back-office) | [Source] BS §3.1; [PI] PI §3 |

### M15 — Offboarding & Archive (ARC)
| ID | Requirement | Label |
|---|---|---|
| FR-ARC-01 | Archive final records, source documents, audit trail under retention policy (longer of legal and contract period); encrypted, immutable, retrievable | [Source] BS §4.2(15), §6.8 |
| FR-ARC-02 | Client export in open formats on completion/termination | [Source] BS §9.7 |
| FR-ARC-03 | After retention: delete or anonymise; deletion certificate on request | [Source] BS §9.7 |

---

## 1.3 Non-functional requirements

### Security (detail in §1.10)
NFR-SEC-01..12 — see §1.10.

### Service levels & KPIs [Source, BS §13] — *indicative; to be validated in pilot, then fixed in contracts*
| ID | Measure | Indicative target |
|---|---|---|
| NFR-SLA-01 | Field-level extraction accuracy on clean docs | ≥ 98%, measured on golden set |
| NFR-SLA-02 | Standard monthly bookkeeping turnaround | 3 business days from complete documents + payment confirmation |
| NFR-SLA-03 | Reviewer first response on flagged item | 1 business day |
| NFR-SLA-04 | Client query response | 1 business day |
| NFR-SLA-05 | Platform availability | 99.5% monthly |
| NFR-SLA-06 | Recovery objectives | RTO 4 h, RPO ≤ 15 min |
| NFR-SLA-07 | Post-delivery error rate | < 1% of entries, reported monthly |

**KPI families [Source, BS §13, §7.8]:** turnaround (by service & region); accuracy (post-review error rate, % accepted without edit); automation (straight-through rate, human minutes/doc); client (CSAT, query resolution time, dispute rate); financial (revenue, collection time, outstanding dues, gross margin/client); compliance (deadlines met, rule-pack currency, audit findings); AI-specific (extraction field accuracy, categorisation override rate, auto-match rate, unreconciled value, rule-citation coverage, reviewer correction rate, tier distribution, calibration gap, AI cost/doc and /task).

### Scalability, availability & operability [Recommended unless noted]
| ID | Requirement |
|---|---|
| NFR-SCL-01 | Stateless API and worker tiers, horizontally scalable; documents processed in parallel by queue workers [Source BS §11.2] |
| NFR-SCL-02 | Durable workflow state (checkpointer) so a crash resumes from last good step [Source BS §8.3] |
| NFR-SCL-03 | Per-task and per-tenant cost and loop limits [Source BS §7.7] |
| NFR-AVL-01 | Model-provider failover via gateway; if none, queue and notify clients of delay [Source BS §8.5] |
| NFR-AVL-02 | Encrypted backups with tested restore meeting RTO/RPO [Source BS §12, §13] |
| NFR-OBS-01 | OpenTelemetry traces for every agent step; structured JSON logs; metrics dashboards [Source BS §8.2] |
| NFR-OBS-02 | Region data-residency options where client requires [Source BS §12] |
| NFR-MNT-01 | Typed code (strict TS; mypy/pyright clean); Pydantic/Zod validation; Alembic migrations; money as `Decimal`/`NUMERIC(20,4)` [PI §13] |
| NFR-MNT-02 | Property-based tests for ledger & tax engines [PI §13] |
| NFR-I18N-01 | English + Urdu UI/messages at minimum; RTL support for Urdu script where shown [Source BS §7.3(12)]; RTL [Recommended] |

---

## 1.4 User roles and permissions matrix

### Roles
| Role | Description | Label |
|---|---|---|
| CLIENT_OWNER | Client owner / finance contact: registers, submits tasks, uploads, answers queries, pays, downloads | [Source] BS §3.1 |
| CLIENT_STAFF | Client employee invited by owner; upload & answer queries; no payment/engagement authority unless granted | [Recommended] |
| SUPPORT_OPS | Client communication, exception handling, onboarding assistance | [Source] BS §3.1 |
| REVIEWER (Reviewer of Record) | Qualified CA / financial expert; reviews & approves; licence recorded | [Source] BS §3.1, §8.7 |
| SECOND_REVIEWER | Qualified reviewer providing four-eyes approval (role assignment; must differ from first approver) | [Source] BS §8.7 |
| LOCAL_PARTNER | Licensed local associate who co-signs in Mode C | [Source] BS §3.3 (role modelling [Recommended]) |
| PLATFORM_ADMIN | Portfolio oversight, pricing, rule-pack governance, payments, risk, provider configuration | [Source] BS §3.1 |
| AI_ENGINEER | Builds/evaluates agents, rule packs (technical), infrastructure; **no** access to client financial data by default | [Source] BS §3.1; data restriction [Recommended] |
| AUDITOR (external, read-only, time-boxed, per engagement) | Receives audit-support pack, raises queries | [Source] BS §6.11 (role modelling [Recommended]) |
| COMPLIANCE_OFFICER (internal auditor) | Read-only audit explorer across tenants for governance | [Recommended] |
| AGENT (system principal) | Each agent has its own service identity with least-privilege tool scopes | [Source] BS §7.7, §8.3 |

### Permissions matrix
Legend: **F** full · **R** read · **O** own tenant/assigned only · **D** draft only (needs human approval) · **A** approve · **—** none

| Capability | Client Owner | Client Staff | Support/Ops | Reviewer | 2nd Reviewer | Local Partner | Platform Admin | AI Engineer | Ext. Auditor | Agent |
|---|---|---|---|---|---|---|---|---|---|---|
| Register / manage org profile | F(O) | R(O) | R | R | R | — | F | — | — | — |
| Invite client staff | F(O) | — | — | — | — | — | F | — | — | — |
| Create task / scope | F(O) | D(O) | F(assist) | R | R | — | F | — | — | D (Intake) |
| Accept quote / sign engagement letter | F(O) | — | — | — | — | — | — | — | — | — |
| Upload documents | F(O) | F(O) | F(assist) | F | — | — | — | — | — | — |
| View task progress | R(O) | R(O) | R | R | R | R(assigned) | R | R (no PII)¹ | — | — |
| Pay advance / balance | F(O) | Grant-only | — | — | — | — | — | — | — | — |
| View invoices & receipts | R(O) | R(O)² | R | — | — | — | F | — | — | — |
| Download final deliverables | R(O, after settlement) | R(O, if granted) | — | R | R | R(assigned) | R | — | R (pack, engagement-scoped) | — |
| View source docs & AI output | R(O) | R(O) | R | F(assigned) | F(assigned) | F(assigned) | R | — ¹ | R (scoped) | Tool-scoped |
| Draft journal entries | — | — | — | F | — | — | — | — | — | D (Posting via ledger service) |
| Approve journals / reconciliations | — | — | — | A | — | — | — | — | — | — |
| Approve tax outputs / final statements | — | — | — | A | A (four-eyes) | A (Mode C co-sign) | — | — | — | — (never) |
| Re-open locked period | — | — | — | A | A (if four-eyes) | — | — | — | — | — |
| Send client message with tax/legal/pricing effect | — | — | D→send after approval | A | — | — | A (pricing) | — | — | D |
| Raise / answer auditor queries | — | — | F | F | — | — | R | — | F (raise) | — |
| Configure pricing / payment models | — | — | — | — | — | — | F | — | — | — |
| Configure Banking Channels providers & gateways | — | — | — | — | — | — | F (back-office) | — | — | — |
| Enable Option B (segregated funds) | — | — | — | A | — | — | A (+ counsel record) | — | — | — |
| Enable Mode A (filing) per jurisdiction | — | — | — | A (licence verified) | — | — | A | — | — | — |
| Rule-pack drafting | — | — | — | F | — | F (local adviser) | F | F (technical) | — | D (RAG agent) |
| Rule-pack activation / promotion | — | — | — | A | — | — | A | — | — | — |
| Threshold / calibration change (loosen) | — | — | — | A | — | — | A | Propose | — | Propose (system) |
| Threshold auto-tighten | — | — | — | notified | — | — | notified | — | — | Automatic (system) |
| Model / prompt release | — | — | — | — | — | — | A | F (after golden set) | — | — |
| Kill switch (tenant / platform) | — | — | — | F (tenant) | — | — | F | F (platform, incident) | — | — |
| Audit explorer | R(O, own trail on request) | — | R | R | R | R(assigned) | R | R (system events, masked) | R (scoped) | — (write-only to log) |
| Delete / anonymise after retention | Request | — | — | — | — | — | A (+ certificate) | — | — | — |

¹ AI Engineer sees masked traces only; access to unmasked client data requires time-boxed, logged break-glass with tenant consent [Recommended].
² Client staff billing visibility is a grant by the owner [Recommended].
Hard rules: no role can edit a posted entry; no agent can approve, file, move money, change prices, or send tax/legal/pricing messages [Source BS §7.7, §8.7]; second reviewer must be a different person from the first approver [Source BS §8.7 / Recommended enforcement].

---

## 1.5 Domestic (Pakistan) and international accounting requirements

### Common to every jurisdiction [Source, BS §6.1–§6.5, §6.10]
- Framework selectable per tenant/country (GAAP, IFRS, IFRS for SMEs, local), read from the Layer 1 pack — **never assumed**.
- Method: accrual or cash, as agreed and applied consistently.
- Principles: double entry, consistency, materiality, prudence, period matching, capital vs revenue separation.
- CoA template 1000–8000 + industry extensions (retail, factory, mall/property, corporate).
- Transaction rules, close checklist and accounting policies as in M6/M7.

### Initial packs — *indicative starting points only; Reviewer verifies the current framework for each client's entity type and size before use* [Source, BS §6.6]
| Pack | Bookkeeping framework (typical) | Tax authority | Typical tax record areas |
|---|---|---|---|
| Pakistan | IFRS and IFRS for SMEs as adopted locally, small-entity framework, company-law requirements | FBR; provincial revenue authorities where applicable | Sales tax, income tax, withholding tax, payroll tax |
| United Kingdom | UK-adopted IFRS, FRS 102, FRS 105 for micro-entities | HMRC | VAT, corporation / self-assessment, PAYE |
| United States | US GAAP; tax-basis books for many small businesses | IRS and state authorities | Federal income tax, state sales tax, payroll tax, 1099/W-2 |
| Canada | ASPE or IFRS | CRA | GST/HST, income tax, payroll remittances |
| Australia | Australian Accounting Standards; simplified rules for small entities | ATO | GST/BAS, income tax, PAYG |

### What each pack must contain before activation [Source, BS §6.6]
- **Layer 1 (bookkeeping/reporting):** permitted frameworks by entity type & size; mandatory books & registers; record-keeping duties; CoA mapping; statement formats & notes; fiscal-year rules; language & currency of records; audit & statutory-filing thresholds; record-retention period.
- **Layer 2 (tax):** tax types, rates, registration thresholds; invoice requirements incl. e-invoicing; withholding, payroll and indirect-tax rules; filing calendar, return templates, penalties, e-filing channels; cross-border rules; effective date for every rule.

> **None of this content is in the Base Standard.** Every rate, threshold, deadline, retention period, statement format and e-filing channel for all five packs is a **gap** (GAP-TAX-01..05 in §1.13) to be sourced from official, current regulator publications and signed off by the Reviewer of Record.

### MVP jurisdiction choice
BS §8.8 / §15 require "Pakistan + **one** international market" for Phase 1. Which one (UK, US, Canada or Australia) is an **open decision** (DEC-01).

---

## 1.6 Tax compliance requirements and delivery modes A–D

### Tax compliance requirements [Source unless noted]
1. Tax computed only by the rule engine from versioned packs; LLM retrieves/explains with citations (BS §8.1).
2. Agents never rely on model memory for rates, deadlines or rules (BS §6.6).
3. All tax outputs go to the Reviewer of Record — Tier D (BS §7.3(8), §7.4).
4. Provisional pack ⇒ all tax outputs and all Tier B items mandatory review; no auto-accept (BS §6.6).
5. Filing calendar & deadline alerts at defined intervals before due date, escalating to Reviewer and client (BS §6.12). *Intervals not defined → GAP.*
6. Tax notices, amendments, late filings per BS §6.12.
7. Tax accounts reconciled to returns and challans (BS §6.5).
8. Cross-border items always to Reviewer (BS §6.6).
9. The Compliance and Tax Agent **does not file anything** (BS §7.3(8)); filing (Mode A) is a human-authorised action.

### Delivery modes [Source, BS §3.3]
| Mode | When it applies | Client receives | AZINCO control |
|---|---|---|---|
| A. Prepare and File | Reviewer of Record is licensed in that jurisdiction | Books, reports and filed returns | Feature flag `filing_enabled` per jurisdiction, **default OFF**; ON only when licence verified (FR-IAM-06), legal authority recorded, Platform Admin + Reviewer approval logged [PI §8] |
| B. Prepare and Hand Over | Platform may not file there | Books, reports, tax-ready records, draft returns for client/local agent to file | Default for international markets until Mode A verified [Recommended] |
| C. Partner-Reviewed | A licensed local associate co-signs | Books, reports, returns co-signed by local associate | LOCAL_PARTNER role must approve in addition to Reviewer |
| D. Bookkeeping Only | Tax out of scope or client's adviser handles tax | Books and reports without tax computation | Tax agent and tax deliverables disabled for the engagement |

Mode is fixed per jurisdiction (and per client where needed), chosen at onboarding, shown in the quote, and written into the contract. Data field: `delivery_mode ∈ {A,B,C,D}` on engagement; allowed modes on jurisdiction config.

---

## 1.7 The 15 agents / services (BS §7.2–§7.3, §8.1–§8.3)

Common contract for all (BS §8.3): typed input/output schemas; invalid output rejected → retried once → escalated; idempotency key; timeout, retry limit, cost cap; checkpoint after every step; least-privilege tools; full trace to Audit Service. Agents call tools; tools call deterministic services; **only the Posting Agent reaches the ledger service, and only to create drafts/posts via it** (BS §7.7). Release 1: all outputs go to Reviewer (BS §8.8).

| # | Agent / service | Inputs | Outputs | Tools (least privilege) | Escalation rules | Label |
|---|---|---|---|---|---|---|
| 1 | **Orchestrator / Supervisor** | Task (state, scope, service type), payment state, agent results | Execution plan, state transitions, escalation records | State graph, task API (read/transition), queue, review-item creator | An agent fails twice; confidence < threshold; ambiguous scope. Hard block: no step before escrow active / engagement confirmed | [Source] §7.3(1) |
| 2 | **Intake & Onboarding** | Client request, profile, uploaded checklist | Structured scope (services, period, deadlines), missing-info list, pack + CoA assignment proposal | Client profile API, rule-pack catalogue (read), checklist service, Communication draft tool | No Active pack or undefined delivery mode → start Jurisdiction Onboarding Protocol | [Source] §7.3(2) |
| 3 | **Document Ingestion (OCR + Vision)** | Clean (scanned) document reference | `Extraction` JSON: doc type, vendor, number, date, currency, lines, tax, totals; per-field confidence; source region (page, bbox) | OCR engine, multimodal model via gateway, document store (read), image pre-processing | Poor legibility; totals mismatch (checked in code); unknown doc type → human manual entry + golden-set case | [Source] §7.3(3), §8.5 |
| 4 | **Validation & Dedup** | Extraction, tenant vendor/customer master, period config | Validation report (pass/fail per check), duplicate candidates, matched counterparties | Arithmetic checker (code), date/period checker, currency validator, hash + fuzzy dedup, master-data lookup | Possible duplicate or mismatch unresolvable automatically | [Source] §7.3(4) |
| 5 | **Bookkeeping Categorisation** | Validated lines, tenant CoA, framework, tenant rules, vendor history | Account + tax-code proposal per line, one-line reason, confidence | Tenant rule engine (applied first), vendor-history lookup, model via gateway (residual only) | Confidence < threshold; capital vs revenue; related party; unusual | [Source] §7.3(5), §8.1 |
| 6 | **Posting & Ledger** | Categorised lines, tax split from rule engine, FX rate from FX service | Draft journal (balanced), posting request to ledger service | **Ledger service** (sole writer), FX service, depreciation/accrual calculators, period-lock check | Entry would not balance; locked period | [Source] §7.3(6) |
| 7 | **Reconciliation** | Ledger, bank/card statements, sub-ledgers, tax returns/challans | Match set (exact → rules → fuzzy), unmatched list with suggested explanations, reconciliation statement (figures from code) | Matching engine, ledger (read), statement parser | Unreconciled difference > tenant tolerance | [Source] §7.3(7) |
| 8 | **Compliance & Tax** | Ledger, tenant pack (versioned), entity profile | Provisional tax positions (computed by rule engine), compliance checks, filing calendar, deadline alerts, tax record pack draft, citations | Rule engine, RAG agent, calendar service | Ambiguous rule; pack out of date; judgemental position. **All tax outputs → Reviewer**. Never files | [Source] §7.3(8) |
| 9 | **Reporting** | Approved ledger & reconciliations, pack Layer 1 formats | TB, P&L, BS, CF, ageing, schedules, management commentary (text only), tax-ready PDFs, cross-refs to working papers | Report engine (figures from ledger), template service, model for commentary | Any identity check fails (from QA) → back to Reviewer | [Source] §7.3(9) |
| 10 | **QA Critic** | Any producer output + evidence | Pass/fail report with findings attached to review item | Re-performance calculators, identity tests (A = L + E), prior-period comparison, policy checker; **different prompt and, where practical, different model** | Any fail → finding on review item | [Source] §7.3(10) |
| 11 | **Anomaly & Risk** | Ledger, transactions, history | Risk score per task & per item; flags (outliers, round numbers, just-below-threshold, unusual vendors, weekend/after-hours, margin shifts, fraud/AML indicators, tax-risk areas) | Statistical detectors (code), model for explanation | High risk → Tier C/D; AML suspicion → Reviewer decides reporting duty | [Source] §7.3(11), §9.6 |
| 12 | **Communication** | Open queries, status events, Reviewer notes | Draft messages (EN/UR), thread summaries | Template + policy checker, notification service (send only non-sensitive status) | Legal / tax-advice / pricing content → human approval; never autonomous | [Source] §7.3(12) |
| 13 | **Billing & Escrow** | Task state, quote, gateway webhooks (via adapter) | Invoices/quotes, payment confirmations, state transitions, deliverable unlock, overdue flags, financial-matrix updates | Payment adapter (read status; create payment links), invoice service, state machine | Payment mismatch, dispute, chargeback, overdue → Admin. **Cannot move money, refund or change prices** | [Source] §7.3(13), §7.7 |
| 14 | **Knowledge / RAG** | Query + jurisdiction + date | Passages with source and effective date | pgvector search over approved sources only | No source found → refuses; never answers from memory | [Source] §7.3(14) |
| 15 | **Audit & Logging Service** (deterministic service, not an LLM) | Events from all agents, services and humans | Append-only, hash-chained audit events | Write-only audit store | Write failure → block the action (fail closed) [Recommended] | [Source] §7.3(15) |

Confidence handling (all producing agents): stated confidence is **calibrated** before use; tier assigned by policy (BS §7.4); in Release 1 tier assignment is computed and logged but every item goes to Reviewer (shadow mode) [Source BS §8.8; shadow logging Recommended].

---

## 1.8 Payment and billing requirements

### 1.8.1 Task & payment state machine [Source, BS §4.3]

| State | Meaning | Allowed next states |
|---|---|---|
| Draft | Task created, scope incomplete | Pending Advance, Cancelled |
| Pending Advance | Quote accepted, advance not received | In Escrow (Work Active), Cancelled |
| In Escrow (Work Active) | Advance received & recorded (ledger status or client-funds account per §5.3); agents processing | Awaiting Client Info, In Review, Disputed |
| Awaiting Client Info | Work paused for missing docs/answers | In Escrow (Work Active) |
| In Review | AI output with the Reviewer of Record | Pending Balance Approval, In Escrow (rework) |
| Pending Balance Approval | Reviewed and approved; balance due | Completed & Settled, Disputed |
| Completed & Settled | Balance paid; deliverables released & archived | Archived |
| Disputed / Cancelled | Under refund & dispute policy | Closed |

**Pay-on-completion variant:** `Pending Advance` → **Engagement Confirmed**; `Pending Balance Approval` → **Pending Payment**. All else unchanged; deliverables locked until payment.

**Client-facing label [PI §3]:** "In Escrow (Work Active)" is a *task status*. Under Option A, UI must add a tooltip/disclosure: "Advance received and committed to your task. Funds are held in AZINCO's operating account, not a segregated escrow account." [Recommended wording; final wording by counsel → DEC-07].

Retainer state handling (monthly cycles) is not specified by the Base Standard → GAP-PAY-03.

### 1.8.2 Payment models [Source, BS §9.3]
| Model | How it works | Controls |
|---|---|---|
| 1. Advance & balance (default) | Advance before work; balance after Reviewer approval; deliverables on balance payment | BS §5 rules; Option A or B |
| 2. Pay on completion | Full fee after task done & approved — approved clients only | Signed engagement, KYC & acceptance, credit limit per client, deliverables locked until paid, revert to Model 1 after any late payment |
| 3. Retainer | Monthly fee billed in advance for agreed volume | Volume bands, overage rate, notice period |

Pricing models (BS §9.2): per-document tiers, fixed-fee packages, monthly retainer by volume band; complexity factors: document count, bank accounts, entities, FX, payroll, inventory, backlog, urgency (rush fee). **No prices are given in the Base Standard** → GAP-PAY-01.

### 1.8.3 Funds handling [Source, BS §5.3; PI §3]
| Item | Option A — Internal ledger status (**default**) | Option B — Legally segregated client-funds account |
|---|---|---|
| Mechanism | Advance received into agency account; tracked against task as In Escrow (Work Active) | Held in separate account (bank escrow, trust or licensed provider) until release conditions met |
| Where money sits | Operating account | Segregated account |
| Release | Recognised as work progresses, per contract | On contract milestone, e.g. after Reviewer approval |
| Refunds | From operating account per refund policy | From segregated account |
| Prerequisites | Clear terms & refund policy in contract | Legal structure, written escrow terms, daily reconciliation, legal confirmation per country |
| Enablement | On by default | **Disabled** until Reviewer of Record + legal counsel approve for that country |
| Storage | `funds_handling = ledger` | `funds_handling = segregated` |

Configurable per tenant / jurisdiction / service by Platform Admin; written into contract; shown to client before payment.

### 1.8.4 Banking Channels & international gateways [PI §3; Source BS §5.2]
- Client-facing: **"Banking Channels"** (Pakistan) and **"Card / PayPal"** (international). Domestic provider names never shown in UI, invoices, emails, documents or API docs. Internal adapter config may hold provider identifiers.
- Adapter interface (all providers): `create_payment_intent`, `get_status`, `verify_webhook`, `parse_webhook`, `fetch_settlement_report`, `refund_request` (human-initiated only).
- Webhooks: signature verified → idempotency key stored → state change → audit event. Daily reconciliation job against settlement reports; mismatches create Admin exceptions.
- FX rate captured at payment time (rate source per platform config) and both currencies stored.
- Release 1: all providers **[SANDBOX]** only.

---

## 1.9 Human-in-the-loop & four-eyes requirements

| ID | Requirement | Label |
|---|---|---|
| HITL-01 | HITL gate created on any Tier C or D condition; in Release 1, on **every** item | [Source] BS §7.5, §8.8 |
| HITL-02 | Panel shows AI entry beside source document (highlighted region), extraction confidence, reasoning, QA & risk findings, rule-pack version & citations | [Source] BS §7.5; PI §7 |
| HITL-03 | Actions: approve, edit, reject & rework, ask client, escalate | [Source] BS §7.5 |
| HITL-04 | Edits never mutate posted entries; an edit before posting replaces the draft; after posting → reversal + repost | [Source] BS §6.4(6) |
| HITL-05 | Approval record: reviewer user ID, name, licence status snapshot, jurisdiction, timestamp, item hash; agents cannot create approvals (DB-level: approval actor must be a human user with REVIEWER role) | [Source] BS §8.7; DB enforcement [Recommended] |
| HITL-06 | Four-eyes: when engagement is high-value or high-risk, release requires a second approval by a different qualified reviewer | [Source] BS §8.7 |
| HITL-07 | Four-eyes trigger rules configurable (value threshold per currency, risk score, new client, cross-border, Provisional pack) | [Recommended] — thresholds are GAP-REV-01 |
| HITL-08 | Mode C requires LOCAL_PARTNER co-sign in addition | [Source] BS §3.3 |
| HITL-09 | Reviewer queue prioritised (deadline, value, risk), pool & delegation; workload planning from volumes | [Source] BS §8.7 |
| HITL-10 | Corrections stored as labelled feedback → evaluation set + tenant-level rules (never cross-tenant) | [Source] BS §7.5, §7.3(5) |
| HITL-11 | Tier D list fixed and never loosened by calibration | [Source] BS §7.4 |
| HITL-12 | Never authorised by an agent: tax filing, final statement sign-off, any payment movement, pricing changes, external tax/legal advice | [Source] BS §7.7; PI §7 |

---

## 1.10 Security & privacy requirements [Source BS §12 unless noted]

| ID | Control | Requirement |
|---|---|---|
| NFR-SEC-01 | Tenant isolation | Separate logical vaults; PostgreSQL RLS on every tenant table; tenant-scoped storage keys; per-tenant encryption keys (BS §8.4) |
| NFR-SEC-02 | Encryption | TLS in transit; AES-256 (or equivalent) at rest |
| NFR-SEC-03 | Access control | RBAC (§1.4); MFA for staff and Reviewers |
| NFR-SEC-04 | Audit | Immutable, append-only, hash-chained logs for all agent & human actions |
| NFR-SEC-05 | Data protection | Alignment with applicable laws (e.g., GDPR for EU/UK, CCPA for California, Pakistan's applicable requirements) — specific obligations are GAP-LEG-03 |
| NFR-SEC-06 | Data residency | Region options where client requires |
| NFR-SEC-07 | Vendor risk | Contracts with model/cloud providers: no training on client data, appropriate retention |
| NFR-SEC-08 | Backup & recovery | Encrypted backups, tested restore, RTO 4h / RPO 15m (BS §13) |
| NFR-SEC-09 | Secrets & payments | Secrets in vault / `.env` (never committed); card data only with PCI gateways |
| NFR-SEC-10 | AML | Client due diligence & monitoring per jurisdiction |
| NFR-SEC-11 | Incident response | Documented plan, breach notification, periodic security testing |
| NFR-SEC-12 | Uploads | Virus scan; type/size limits; signed time-limited download URLs [PI §11] |
| NFR-SEC-13 | AI safety | Prompt-injection defence (document text = data); output schema validation; least-privilege tools; PII masking in logs & prompts; cost/loop limits; kill switch (BS §7.7) |
| NFR-SEC-14 | No cross-tenant learning | Client data never used to train shared models; tenant rules isolated (BS §2.6, §7.6) |
| NFR-SEC-15 | Payments | Webhook signature verification & idempotency (BS §5.2) |
| NFR-SEC-16 | Dev data | Synthetic data only; no real client data in development without written authorisation [PI §11] |
| NFR-SEC-17 | Retention & deletion | Retention = longer of legal and contract period; deletion/anonymisation + certificate (BS §6.8, §9.7) |
| NFR-SEC-18 | AppSec baseline | OWASP ASVS L2 target, dependency & container scanning, SAST in CI, rate limiting, CSRF/CORS policy [Recommended] |

---

## 1.11 Client lifecycle

| Stage | Steps | Controls / outputs | Source |
|---|---|---|---|
| 1. Registration | Account, email verification, MFA option | User + pending org | BS §10.1 |
| 2. Onboarding & KYC | Business type, jurisdiction, entity, tax IDs, FYE, currency, method; identity/business verification | Tenant vault, pack & CoA assigned | BS §4.1, §4.2(1) |
| 3. Acceptance / AML | Sanctions & PEP screening, conflicts/independence, delivery-mode availability; source-of-funds for large/unusual receipts | Accept / reject / escalate to Reviewer | BS §9.6 |
| 4. Jurisdiction check | Active pack? else Onboarding Protocol (Provisional) | Pack status recorded | BS §6.6 |
| 5. Engagement letter | Generated, reviewed, e-signed; payment model & funds-handling & delivery mode fixed | Signed letter (immutable copy) | BS §9.1, §9.3 |
| 6. Opening balances & migration | Opening TB, imports, cut-over, migrated periods locked | Reviewer-approved opening position | BS §6.9 |
| 7. Task & quote | Scope, checklist, quote, acceptance | Task: Draft → Pending Advance / Engagement Confirmed | BS §4.2(2–3), §9.2 |
| 8. Advance / confirmation | Banking Channels or gateway payment; FX captured | In Escrow (Work Active) | BS §5.1 |
| 9. Processing | Intake → ingestion → validation → categorisation → posting (draft) → reconciliation → tax → QA → risk | Review items | BS §4.2(4–10) |
| 10. Queries | Awaiting Client Info; reminders; clock stops | Answers attached to items | BS §9.5 |
| 11. Scope change | Change request + revised quote; accepted before extra work | New quote line | BS §9.4 |
| 12. Review & approval | Reviewer (+ second reviewer / local partner) | Approvals with licence snapshot | BS §4.2(13), §8.7 |
| 13. Balance & delivery | Balance paid → deliverables unlock | Completed & Settled | BS §4.2(14) |
| 14. Post-delivery errors | Reversal & re-issue; root cause | Corrected deliverable | BS §9.4 |
| 15. Recurring cycles | Month-end / year-end close, audit support, notices | Close calendar | BS §6.11–§6.12 |
| 16. Offboarding | Export in open formats | Export bundle | BS §9.7 |
| 17. Archive & deletion | Retention, then delete/anonymise; certificate | Archive; deletion certificate | BS §6.8, §9.7 |

---

## 1.12 Requirements Traceability Matrix (RTM)

Phases: P0 Foundation · P1 MVP · P2 Automation · P3 Scale · P4 Optimise (BS §15).
Test methods: **UT** unit · **PBT** property-based · **IT** integration · **E2E** end-to-end · **SEC** security test/pen test · **GS** golden-set evaluation · **REV** Reviewer sign-off / inspection · **DOC** document/legal review · **OPS** operational drill.

| ID | Requirement (short) | BS § | Module | Phase | Test method |
|---|---|---|---|---|---|
| FR-IAM-01 | Client registration | 10.1 | IAM | P0 | IT, E2E |
| FR-IAM-02 | Tenant vault per client | 4.1, 17 | IAM | P0 | IT, SEC |
| FR-IAM-03 | RBAC matrix | 12 | IAM | P0 | UT, IT, SEC |
| FR-IAM-04 | MFA for staff/reviewers | 12 | IAM | P0 | IT, SEC |
| FR-IAM-06 | Reviewer licence register | 8.7, 9.6 | IAM | P1 | IT, REV |
| FR-IAM-08 | EN/UR language preference | 7.3(12), 10.1 | IAM | P1 | E2E |
| FR-ONB-01..03 | Business profile, pack & CoA assignment | 4.1, 4.2, 6.2 | ONB | P1 | IT, E2E |
| FR-ONB-04 | Jurisdiction Onboarding Protocol trigger | 3.3, 6.6 | ONB/TAX | P1 (trigger), P3 (full) | IT, REV |
| FR-ONB-05..06 | KYC, sanctions/PEP, conflicts | 9.6 | ONB | P1 | IT, DOC |
| FR-ONB-07 | Delivery mode at onboarding | 3.3 | ONB | P1 | IT, DOC |
| FR-ONB-08 | Engagement letter + e-sign | 9.1 | ONB | P1 | DOC, E2E |
| FR-ONB-09 | Payment model per client | 9.3 | ONB/PAY | P1 | IT |
| FR-ONB-10 | funds_handling flag | 5.1, 5.3 | ONB/PAY | P0 (schema), P1 | UT, IT |
| FR-ONB-11..14 | Opening balances & migration | 6.9 | ONB/LED | P1 | IT, REV |
| FR-ONB-16 | Accounting policies per tenant | 6.10 | ONB | P1 | IT |
| FR-TSK-01..03 | Task, checklist, quote | 4.2, 9.2, 9.5 | TSK | P1 | IT, E2E |
| FR-TSK-04 | State machine | 4.3 | TSK | P0 (engine), P1 | UT, PBT, IT |
| FR-TSK-05 | Change request | 9.4 | TSK | P1 | IT |
| FR-TSK-06 | Pause clock on client info | 9.5 | TSK | P1 | UT, IT |
| FR-TSK-07 | Progress tracker | 4.1, 10.1 | TSK | P1 | E2E |
| FR-DOC-01 | Upload channels (drag-drop P1; email-in, camera P2) | 10.1 | DOC | P1/P2 | E2E |
| FR-DOC-02 | Virus scan | 4.2(4), 12 | DOC | P1 | IT, SEC |
| FR-DOC-03 | Hash dedup | 4.2(4), 6.4(2) | DOC | P1 | UT |
| FR-DOC-05..06 | Encrypted storage, signed URLs | 12 | DOC | P0 (baseline), P1 | IT, SEC |
| FR-EXT-01..03 | OCR/vision extraction with confidence & region | 7.3(3) | EXT | P1 | GS, IT |
| FR-EXT-04 | Validation & fuzzy dedup | 7.3(4) | EXT | P1 | UT, GS |
| FR-EXT-05 | OCR failure → manual entry | 8.5 | EXT | P1 | IT |
| FR-LED-01 | CoA template + extensions | 6.2 | LED | P1 | UT, REV |
| FR-LED-02 | Rules-first categorisation | 7.3(5), 8.1 | LED | P1 | GS |
| FR-LED-03 | DR = CR in service & DB | 8.4 | LED | P0 (schema), P1 | PBT, IT |
| FR-LED-04 | Immutability, reversal only | 6.4(6), 8.4 | LED | P0 (schema), P1 | PBT, SEC |
| FR-LED-05 | Evidence links on every line | 6.4(1), 8.4 | LED | P1 | IT |
| FR-LED-06 | Suspense for unsupported | 6.4(5) | LED | P1 | UT |
| FR-LED-07 | Tax split by rule engine | 6.4(4) | LED/TAX | P1 | UT, PBT |
| FR-LED-08 | FX at transaction date + revaluation | 6.4(3) | LED | P1 | UT, PBT |
| FR-LED-09 | Period lock & controlled re-open | 6.5, 6.11, 8.4 | LED | P1 | IT, SEC |
| FR-LED-10..11 | Accruals, depreciation, inventory, payroll journals | 6.10 | LED | P2 | UT, PBT, REV |
| FR-LED-12 | Related party = Tier D | 6.10 | LED/REV | P1 | UT |
| FR-LED-14 | Multi-entity consolidation | 6.2 | LED | P3 | IT, REV |
| FR-LED-15 | Hash-chained ledger audit | 8.2 | LED | P0 | UT, SEC |
| FR-REC-01 | Bank reconciliation matching | 7.3(7) | REC | P1 | GS, IT |
| FR-REC-02..04 | Sub-ledger/tax recs & close checklist | 6.5 | REC | P2 | IT, REV |
| FR-REC-05..06 | Year-end & audit-support pack | 6.11 | REC | P2 | REV |
| FR-TAX-01..02 | Two-layer versioned packs + status | 6.6 | TAX | P0 (governance/schema), P1 (PK + 1) | UT, REV |
| FR-TAX-03..04 | Onboarding protocol & re-review cadence | 6.6 | TAX | P3 | REV, OPS |
| FR-TAX-05 | Rule-engine tax computation | 6.6, 7.3(8), 8.1 | TAX | P2 | PBT, GS, REV |
| FR-TAX-06 | Deadline alerts | 6.12 | TAX | P2 | IT |
| FR-TAX-07 | Tax pack with citations | 6.7 | TAX/RPT | P2 | REV |
| FR-TAX-08 | Multi-country tenant | 6.6 | TAX | P3 | IT, REV |
| FR-TAX-09..10 | Notices & amendments | 6.12 | TAX | P3 | IT, REV |
| FR-TAX-11 | Mode A flag default off | 3.3 | TAX | P0 (flag) | UT, DOC |
| FR-REV-01..03 | Queue, side-by-side, actions | 7.5, 8.7, 10.2 | REV | P1 | E2E, REV |
| FR-REV-04 | Human-only approvals with licence | 8.7 | REV | P1 | IT, SEC |
| FR-REV-05 | Four-eyes | 8.7 | REV | P1 | IT |
| FR-REV-06 | Corrections as labelled feedback | 7.5 | REV/AGT | P1 | IT |
| FR-REV-07 | All items to Reviewer in R1 | 8.8 | REV | P1 | IT |
| FR-REV-08 | Tier D always human | 7.4 | REV/AGT | P1 | UT, SEC |
| FR-RPT-01..03 | Standard deliverables, code-computed | 6.7, 2.9 | RPT | P1 (TB, GL, bank rec), P2 (rest) | IT, REV |
| FR-RPT-04 | Deliverables locked until settled | 5.1 | RPT/PAY | P1 | IT, E2E |
| FR-PAY-01..02 | Banking Channels adapter & naming | PI §3 (BS 5.2) | PAY | P1 | IT, UI review |
| FR-PAY-03 | International gateway (one, sandbox) | 5.2 | PAY | P1 | IT |
| FR-PAY-04 | Idempotent signed webhooks + daily rec | 5.2 | PAY | P1 | IT, SEC, OPS |
| FR-PAY-05 | FX at payment | 5.1 | PAY | P1 | UT |
| FR-PAY-07 | Three payment models | 9.3 | PAY | P1 (Model 1), P2 (2, 3) | IT |
| FR-PAY-08 | Option A default, B disabled | 5.3 | PAY | P0 (flag), P1 | UT, DOC |
| FR-PAY-10 | Agency financial matrix | 5.4 | PAY/ADM | P1 | IT |
| FR-COM-01 | Secure chat | 10.1 | COM | P1 | E2E |
| FR-COM-02..03 | Communication Agent, approval for sensitive | 7.3(12) | COM | P3 | IT, REV |
| FR-AGT-01 | State graph orchestration | 7.1, 8.2 | AGT | P1 | IT |
| FR-AGT-02 | Model gateway | 8.2, 8.8 | AGT | P1 | IT |
| FR-AGT-03 | Step contract | 8.3 | AGT | P1 | UT, IT |
| FR-AGT-04..05 | Confidence policy & calibration | 7.4 | AGT | P2 | GS, REV |
| FR-AGT-06 | Model registry | 8.6 | AGT | P1 | IT |
| FR-AGT-07 | Golden set & regression | 7.8, 8.6 | AGT | P0 (framework), P1 | GS |
| FR-AGT-08 | Kill switch & limits | 7.7, 8.5 | AGT | P1 | IT, OPS |
| FR-ADM-01 | Immutable audit log | 7.3(15), 12 | ADM | P0 | UT, SEC |
| FR-ADM-02 | Audit explorer | 10.2 | ADM | P1 (basic), P2 (full trace) | E2E, REV |
| FR-ADM-03 | Portfolio overview | 10.2 | ADM | P1 | E2E |
| FR-ADM-04 | Rule-pack manager | 10.2 | ADM | P1 | E2E, REV |
| FR-ADM-05 | Threshold/calibration manager | 10.2 | ADM | P2 | E2E, REV |
| FR-ADM-06 | Agent operations view | 10.2 | ADM | P2 | E2E |
| FR-ADM-07 | Change control | 16 | ADM | P0 (process), P1 | DOC, REV |
| FR-ARC-01..03 | Archive, export, deletion | 6.8, 9.7 | ARC | P2 | IT, DOC |
| NFR-SLA-01 | Extraction ≥ 98% | 13 | AGT | P1 exit | GS |
| NFR-SLA-02..04 | Turnaround & response targets | 13 | OPS | P1 pilot | OPS |
| NFR-SLA-05..06 | 99.5%, RTO 4h / RPO 15m | 13 | Infra | P2 | OPS |
| NFR-SLA-07 | Post-delivery errors < 1% | 13 | QA | P2 | GS, OPS |
| NFR-SEC-01 | RLS tenant isolation | 12, 8.4 | Infra | P0 | SEC, IT |
| NFR-SEC-02 | Encryption in transit/at rest | 12 | Infra | P0 | SEC |
| NFR-SEC-09 | Secrets management | 12 | Infra | P0 | SEC |
| NFR-SEC-13 | Prompt-injection & AI safety | 7.7, 8.5, 8.6 | AGT | P1 | SEC, GS |
| NFR-SEC-16 | Synthetic dev data | PI §11 | All | P0 | DOC |
| HITL-01..12 | Human-in-the-loop & four-eyes | 7.4, 7.5, 8.7 | REV | P1 | IT, SEC, REV |

---

## 1.13 Gaps, ambiguities, risks and open decisions

### A. Base Standard Appendix A (20 deficiencies) — status in AZINCO
All 20 are marked resolved in the Base Standard; AZINCO carries each into a requirement. [Source BS App. A]

| # | Gap (BS) | BS resolution § | AZINCO coverage |
|---|---|---|---|
| 1 | What runs the agents | 8.2 | FR-AGT-01..09 |
| 2 | LLM producing wrong figures | 2, 8.1 | FR-RPT-03, FR-LED-07/08/10, FR-TAX-05 |
| 3 | No agent execution contract | 8.3 | FR-AGT-03 |
| 4 | Ledger invariants implied | 8.4 | FR-LED-03..05, 09 |
| 5 | No failure / degraded modes | 8.5 | NFR-AVL-01, FR-EXT-05, FR-AGT-08 |
| 6 | Thin model/prompt change control | 8.6 | FR-AGT-06/07, FR-ADM-07 |
| 7 | Reviewer capacity & second review | 8.7 | HITL-06, HITL-09 |
| 8 | No first-release build | 8.8 | Part 5 roadmap |
| 9 | Payment timing vs real practice | 5, 9.3 | FR-PAY-07 |
| 10 | No engagement letter | 9.1 | FR-ONB-08 |
| 11 | No pricing structure | 9.2 | FR-TSK-03 (prices themselves = GAP-PAY-01) |
| 12 | No scope-change rule | 9.4 | FR-TSK-05, FR-TSK-08 |
| 13 | Existing books not covered | 6.9 | FR-ONB-11..14 |
| 14 | Accounting policies not stated | 6.10 | FR-ONB-16, FR-LED-11..13 |
| 15 | Year-end & audit support missing | 6.11 | FR-REC-05..06 |
| 16 | Tax notices/amendments | 6.12 | FR-TAX-09..10 |
| 17 | Acceptance, AML, sanctions | 9.6 | FR-ONB-05..06 |
| 18 | No offboarding | 9.7 | FR-ARC-02..03 |
| 19 | No numeric targets | 13 | NFR-SLA-01..07 |
| 20 | Risk register incomplete | 14 | §1.13 D below |

**Decisions the Base Standard leaves with owners [Source BS App. A]:** final payment model per client segment (DEC-03), delivery mode per country (DEC-02), threshold values after calibration (DEC-05), legal wording of engagement letter confirmed by local counsel (DEC-06).

### B. Content gaps — data the Base Standard does not provide (must NOT be invented)
| ID | Gap | Why it matters | Owner | Label |
|---|---|---|---|---|
| GAP-TAX-01 | Pakistan pack content: sales-tax / income-tax / WHT / payroll rates, thresholds, filing calendar, return templates, penalties, e-filing channels, provincial authority split, record-retention period | Needed before any tax computation | Reviewer of Record + PK tax counsel | [Source gap] |
| GAP-TAX-02 | UK pack content (VAT, CT/SA, PAYE rates, MTD/e-filing, retention) | Same | Reviewer + UK adviser | [Source gap] |
| GAP-TAX-03 | US pack content (federal, **per-state** sales tax, payroll, 1099/W-2 rules) — state variation is large | Same; scoping risk | Reviewer + US adviser | [Source gap] |
| GAP-TAX-04 | Canada pack content (GST/HST by province, income tax, payroll remittances) | Same | Reviewer + CA adviser | [Source gap] |
| GAP-TAX-05 | Australia pack content (GST/BAS, income tax, PAYG) | Same | Reviewer + AU adviser | [Source gap] |
| GAP-TAX-06 | Deadline-alert intervals ("defined intervals") | Alert scheduling | Reviewer | [Source gap] |
| GAP-ACC-01 | Statement formats & notes per framework/pack | Reporting templates | Reviewer | [Source gap] |
| GAP-ACC-02 | Reconciliation tolerance defaults per tenant | Escalation rule | Reviewer | [Source gap] |
| GAP-ACC-03 | Capitalisation thresholds, useful lives defaults | Fixed-asset engine | Reviewer per tenant | [Source gap] |
| GAP-ACC-04 | FX rate source per currency (e.g., central-bank reference vs provider) | FX determinism | Platform Admin + Reviewer | [Source gap] |
| GAP-PAY-01 | Price list, advance %, rush fee, overage rates | Quotes | Platform Admin | [Source gap] |
| GAP-PAY-02 | Refund & dispute policy text and timelines | Disputed/Cancelled state | Admin + counsel | [Source gap] |
| GAP-PAY-03 | Retainer task-state handling (monthly cycle mapping to §4.3) | State machine | Admin | [Source gap] |
| GAP-PAY-04 | Credit-limit rules for pay-on-completion; definition of "late payment" | Model 2 controls | Admin | [Source gap] |
| GAP-PAY-05 | Which Banking Channels providers, their APIs, settlement-report formats, and merchant onboarding status | Adapter build | Platform Admin | [PI gap] |
| GAP-REV-01 | Four-eyes trigger: "high-value / high-risk" thresholds | HITL-06 | Reviewer | [Source gap] |
| GAP-REV-02 | Licence verification method per jurisdiction (which bodies, evidence) | Mode A/C | Reviewer + counsel | [Source gap] |
| GAP-AGT-01 | V_max per client & currency | Tier logic | Reviewer | [Source gap] |
| GAP-AGT-02 | Golden test set: no documents exist yet (Summary confirms no sample records) — need anonymised/synthetic sets per jurisdiction & business type | Every exit gate | Reviewer + AI Engineer | [Source gap] |
| GAP-AGT-03 | Per-task cost caps and loop limits (numbers) | Safety | AI Engineer | [Source gap] |
| GAP-LEG-01 | Legal/licensing review per jurisdiction (Phase 0 output) | Mode selection | Counsel | [Source gap] |
| GAP-LEG-02 | Client-money treatment per country (needed for Option B) | Option B | Counsel | [Source gap] |
| GAP-LEG-03 | Concrete privacy obligations (GDPR/UK GDPR, CCPA, Pakistan), DPA templates, breach timelines | NFR-SEC-05 | Counsel | [Source gap] |
| GAP-LEG-04 | AML reporting duties per jurisdiction | FR-ONB-05 | Counsel + Reviewer | [Source gap] |
| GAP-LEG-05 | Legal retention period per jurisdiction | Archive | Counsel | [Source gap] |
| GAP-OPS-01 | KYC / sanctions / PEP data provider | Acceptance | Admin | [Source gap] |
| GAP-OPS-02 | Hosting region(s) & data-residency offering | NFR-SEC-06 | Admin | [Source gap] |
| GAP-OPS-03 | Response period for "Awaiting Client Info" & reminder cadence | FR-TSK-06 | Admin (contract) | [Source gap] |

### C. Ambiguities / inconsistencies in the sources
| ID | Ambiguity | Proposed resolution | Label |
|---|---|---|---|
| AMB-01 | §8.8 says "five agents first" but lists six (Ingestion, Validation, Categorisation, Posting, Reconciliation **+ QA Critic**) | Treat as 5 producers + QA Critic = 6 agents in Phase 1, plus Orchestrator as the graph supervisor | [Recommended] |
| AMB-02 | §15 Phase 1 lists ingestion, categorisation, reconciliation; Phase 2 "adds validation, posting… QA Critic, audit logging" — but §8.8 puts Validation, Posting and QA Critic in the first release | Follow §8.8 (more specific, and posting is needed for reconciliation). Phase 2 then *automates* them (tiers) rather than introducing them. PI §12 also follows §8.8 | [Recommended] |
| AMB-03 | §15 puts audit logging in Phase 2; §2.7 and §12 require full auditability always | Build audit log in Phase 0 (PI §12) | [Recommended] |
| AMB-04 | §5.1 "No processing before advance" vs pay-on-completion model | §2.3 and §4.3 resolve it: Engagement Confirmed replaces Pending Advance for approved clients | [Source] |
| AMB-05 | §7.3(6) Posting Agent "writes" via ledger service vs PI §6 "agents never write directly to the posted ledger" | Posting Agent may only create **draft** journals through the ledger service; transition draft → posted requires Reviewer approval (R1) or a Tier A policy decision (P2+), executed by the ledger service | [Recommended] |
| AMB-06 | "Escrow" wording could imply legal segregation | Option A labelled as task status with disclosure; never called legal escrow (PI §3) | [PI] |
| AMB-07 | "Second reviewer" qualifications not defined (same licence level? same jurisdiction?) | Must hold REVIEWER role with valid licence for the engagement's jurisdiction and differ from first approver; confirm | [Recommended] → DEC-08 |
| AMB-08 | §2.1 "No … client-facing sign-off is released without Reviewer approval" vs Communication Agent sending "progress updates" | Pure status updates from approved templates may be auto-sent; any free-text or tax/legal/pricing content needs approval | [Recommended] |
| AMB-09 | Payroll "records" vs payroll processing | AZINCO prepares payroll **accounting records/journals** only; does not run payroll payments | [Source BS §6.10, PI §4] |
| AMB-10 | "Auditor" role in prompt vs BS (auditor appears only as receiver of audit-support pack) | Model as time-boxed, read-only external role per engagement | [Recommended] |
| AMB-11 | Summary says gateways include JazzCash/EasyPaisa | Overridden by PI §3 → "Banking Channels" | [PI] |

### D. Key risks (BS §14 + AZINCO-specific)
| ID | Risk | Control | Label |
|---|---|---|---|
| RSK-01..18 | All 18 risks of BS §14 (incorrect tax rules, OCR error, hallucinated entries, data leak, prompt injection, unlicensed practice, payment fraud, over-reliance on automation, single-reviewer dependency, model change, no-pack country, loose thresholds, client funds mishandled, pay-on-completion non-payment, provider outage, reviewer error/capacity, scope creep, ML/sanctions, wrong opening balances) | Controls as listed in BS §14 and mapped in this document | [Source] |
| RSK-19 | Golden set unavailable → exit gates cannot be evaluated | Synthetic + anonymised (with written consent) dataset programme in Phase 0 | [Recommended] |
| RSK-20 | Reviewer of Record availability for building 5 packs in parallel | MVP = PK + 1 market only; others Phase 3 | [Recommended] |
| RSK-21 | Domestic payment-provider API instability / settlement-report formats | Adapter abstraction; manual reconciliation fallback; [SANDBOX] until verified | [Recommended] |
| RSK-22 | LLM cost overrun on OCR-heavy workloads | Gateway budget caps, per-doc cost KPI, OCR-first then vision only on low confidence | [Recommended] |
| RSK-23 | Urdu / handwritten document accuracy below target | Track per-language accuracy; route to human; expand golden set | [Recommended] |
| RSK-24 | Misleading "escrow" language → consumer-protection exposure | Wording review by counsel (DEC-07) | [PI] |
| RSK-25 | US multi-state sales tax scope explosion if US chosen as first market | Choose UK/CA/AU first or limit US to federal + 1 state | [Recommended] |

### E. Open decisions (owner action required)
| ID | Decision | Options / recommendation | Owner | Label |
|---|---|---|---|---|
| DEC-01 | First international market for MVP | Recommend **UK** (one VAT regime, time-zone overlap, English) — confirm | Owner + Reviewer | [Recommended] |
| DEC-02 | Delivery mode per jurisdiction | Recommend PK: B until licence verified (A later); UK/US/CA/AU: B or D at launch | Reviewer + counsel | [Source] App. A |
| DEC-03 | Payment model per client segment | Default Model 1; Model 2 for approved repeat clients; Model 3 Phase 2 | Platform Admin | [Source] App. A |
| DEC-04 | Orchestration framework | LangGraph (persistent checkpointer, interrupts) for the graph; OpenAI Agents SDK optional for individual agents behind gateway — ADR in Phase 0 | AI Engineer | [Recommended] |
| DEC-05 | Threshold values after calibration | Defaults T_auto 98%, T_floor 95%, Tier B sample 20%, Tier A audit 5%, N_min 200 until calibrated | Reviewer | [Source] BS §7.4 |
| DEC-06 | Engagement-letter legal wording | Counsel per country | Counsel | [Source] App. A |
| DEC-07 | Client-facing wording of "In Escrow (Work Active)" under Option A | Draft disclosure in §1.8.1 for counsel review | Counsel | [PI] |
| DEC-08 | Second-reviewer qualification rule | See AMB-07 | Reviewer | [Recommended] |
| DEC-09 | OCR engine (open-source vs cloud) & initial model set | ADR in Phase 0 after cost/accuracy spike on synthetic set | AI Engineer | [Recommended] |
| DEC-10 | Hosting provider & region; KMS | ADR in Phase 0 | Owner | [Recommended] |
| DEC-11 | Auth approach (self-hosted FastAPI auth vs managed IdP) | ADR in Phase 0 | Owner + Engineer | [Recommended] |
| DEC-12 | Platform base currency | **RESOLVED 2026-11-17: PKR** (owner decision). Client currency still stored per payment with FX rate (BS §5.1) | Owner | [Owner decision] |
| DEC-13 | Who is the named Reviewer of Record for Phase 1, and their licence(s) | Required before any approval flow goes live | Owner | [Source] |

---

## Part 1 — Summary of coverage

| # | Item | Status | Notes |
|---|---|---|---|
| 1.1 | Overview & business objectives | Done | 9 objectives, scope in/out |
| 1.2 | Functional requirements | Done | 15 modules, ~130 FRs with IDs |
| 1.3 | Non-functional requirements | Done | BS §13 targets marked *indicative* |
| 1.4 | Roles & permissions | Done | 11 roles; matrix of 26 capabilities |
| 1.5 | Pakistan & international accounting | Done | Indicative packs only; all rule content = gaps |
| 1.6 | Tax compliance & Modes A–D | Done | Mode A default OFF |
| 1.7 | 15 agents/services | Done | Inputs, outputs, tools, escalation |
| 1.8 | Payments & billing | Done | State machine, 3 models, Option A/B, Banking Channels |
| 1.9 | HITL & four-eyes | Done | 12 requirements |
| 1.10 | Security & privacy | Done | 18 controls |
| 1.11 | Client lifecycle | Done | 17 stages |
| 1.12 | Traceability Matrix | Done | ~95 rows, phase + test method |
| 1.13 | Gaps, ambiguities, risks, decisions | Done | 20 App. A items, 28 gaps, 11 ambiguities, 25 risks, 13 decisions |
