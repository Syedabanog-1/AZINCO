// Public-site copy. Client-facing payment wording follows Project Instructions §3:
// domestic payments are always "Banking Channels".

export const PRINCIPLES = [
  {
    title: "Every figure is calculated by tested code",
    body: "AI reads and proposes; amounts, tax, FX and balances come from deterministic engines.",
  },
  {
    title: "Every entry links to its evidence",
    body: "Each journal line points to the source document, page and field it came from.",
  },
  {
    title: "A qualified human signs off",
    body: "Statements and tax records are approved by a Reviewer of Record — never by an AI agent.",
  },
  {
    title: "Your data stays yours",
    body: "Isolated per client, encrypted, fully audited, and never used to train shared models.",
  },
] as const;

export const SERVICES = [
  { title: "Bookkeeping & general ledger", body: "Double-entry books on a chart of accounts tailored to your business type." },
  { title: "Bank & cash reconciliation", body: "Statements matched to your ledger with every difference explained." },
  { title: "Payables & receivables", body: "Supplier and customer ledgers with ageing reports." },
  { title: "Financial statements", body: "Trial balance, profit & loss, balance sheet and cash flow in your framework." },
  { title: "Tax-ready records", body: "Sales tax / VAT / GST and income-tax working papers with rule citations." },
  { title: "Inventory, assets & payroll records", body: "Stock, fixed-asset registers, depreciation and payroll journals." },
] as const;

export const JOURNEY = [
  { title: "Onboarding", body: "Business profile, verification and engagement letter." },
  { title: "Task & advance", body: "Choose services, upload documents, pay the advance." },
  { title: "AI processing", body: "Documents read, categorised and reconciled — as drafts." },
  { title: "Expert review", body: "A Reviewer of Record checks and approves every item." },
  { title: "Delivery", body: "Settle the balance and download audit-ready deliverables." },
] as const;

export const DELIVERY_MODES = [
  { code: "A", title: "Prepare and file", body: "Where our reviewer is licensed and authorised to file." },
  { code: "B", title: "Prepare and hand over", body: "Books, reports and draft returns for you or your agent to file." },
  { code: "C", title: "Partner-reviewed", body: "Co-signed by a licensed local associate." },
  { code: "D", title: "Bookkeeping only", body: "Books and reports without tax computation." },
] as const;

// Owner decision 2026-11-17: reporting in both PKR and USD; PKR is the primary base currency.
export const REPORTING_CURRENCIES = ["PKR", "USD"] as const;

export const JURISDICTIONS = [
  "Pakistan",
  "United Kingdom",
  "United States",
  "Canada",
  "Australia",
] as const;

export type PlannedInterface = {
  title: string;
  phase: string;
  items: readonly string[];
};

export const PLANNED: Record<"login" | "dashboard" | "review" | "admin", PlannedInterface> = {
  login: {
    title: "Sign in & registration",
    phase: "Step 0.7 — authentication with MFA",
    items: ["Email + password (Argon2id)", "TOTP multi-factor authentication", "Session management"],
  },
  dashboard: {
    title: "Client dashboard",
    phase: "Phase 1 — MVP",
    items: ["Task progress across the 5 stages", "Document upload", "Invoices via Banking Channels or Card (Stripe)", "Downloads after settlement"],
  },
  review: {
    title: "Reviewer of Record dashboard",
    phase: "Phase 1 — MVP",
    items: ["Prioritised review queue", "Source document side by side with AI draft", "Approve, edit, reject, ask client", "Four-eyes second review"],
  },
  admin: {
    title: "Platform Admin console",
    phase: "Phase 1 — MVP",
    items: ["Portfolio overview", "Rule-pack manager", "Banking Channels & gateway settings", "Audit explorer"],
  },
};
