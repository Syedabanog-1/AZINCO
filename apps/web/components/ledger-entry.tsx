/**
 * Hero illustration: one journal entry moving from source document to reviewer sign-off.
 * All values are SYNTHETIC sample data and are labelled as such on screen.
 * The totals are computed here (not typed in) so the sample always balances.
 */

const LINES = [
  { account: "6120 Office supplies", side: "dr", amount: 42_500, evidence: "Invoice p.1, line total" },
  { account: "2100 Accounts payable", side: "cr", amount: 42_500, evidence: "Invoice p.1, supplier" },
] as const;

const pkr = new Intl.NumberFormat("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function LedgerEntry() {
  const debit = LINES.filter((l) => l.side === "dr").reduce((s, l) => s + l.amount, 0);
  const credit = LINES.filter((l) => l.side === "cr").reduce((s, l) => s + l.amount, 0);
  const balanced = debit === credit;

  return (
    <figure className="relative" aria-label="Sample journal entry with reviewer approval">
      <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-[0_1px_0_var(--color-line),0_24px_48px_-24px_rgba(15,76,66,0.35)]">
        <div className="flex items-center justify-between border-b border-line bg-paper px-5 py-3 text-sm">
          <span className="font-semibold">Journal entry JE-0142</span>
          <span className="text-ink-faint">Sample, synthetic data</span>
        </div>

        <div className="border-b border-line-soft px-5 py-3 text-sm text-ink-soft">
          Source: supplier invoice INV-0142.pdf, read by the ingestion agent and drafted for review.
        </div>

        {/* Ledger paper: ruled rows and a margin rule on the left. */}
        <table className="figures w-full text-sm">
          <caption className="sr-only">Journal lines in PKR</caption>
          <thead>
            <tr className="border-b border-line text-left text-ink-faint">
              <th scope="col" className="py-2 pr-2 pl-5 font-medium">Account</th>
              <th scope="col" className="px-2 py-2 text-right font-medium">Debit</th>
              <th scope="col" className="py-2 pr-5 pl-2 text-right font-medium">Credit</th>
            </tr>
          </thead>
          <tbody>
            {LINES.map((l) => (
              <tr key={l.account} className="border-b border-line-soft">
                <td className="border-l-2 border-fail/40 py-3 pr-2 pl-[18px]">
                  <span className={l.side === "cr" ? "pl-6" : ""}>{l.account}</span>
                  <span className="mt-0.5 block text-xs text-ink-faint">{l.evidence}</span>
                </td>
                <td className="px-2 py-3 text-right align-top">{l.side === "dr" ? pkr.format(l.amount) : ""}</td>
                <td className="py-3 pr-5 pl-2 text-right align-top">{l.side === "cr" ? pkr.format(l.amount) : ""}</td>
              </tr>
            ))}
            <tr className="font-semibold">
              <td className="py-3 pr-2 pl-5">Total, PKR</td>
              <td className="px-2 py-3 text-right">
                <span className="border-b-[3px] border-double border-ink pb-0.5">{pkr.format(debit)}</span>
              </td>
              <td className="py-3 pr-5 pl-2 text-right">
                <span className="border-b-[3px] border-double border-ink pb-0.5">{pkr.format(credit)}</span>
              </td>
            </tr>
          </tbody>
        </table>

        <ol className="grid grid-cols-3 border-t border-line text-xs">
          <li className="px-4 py-3">
            <span className="block font-semibold text-ink">Prepared</span>
            <span className="text-ink-faint">AI draft</span>
          </li>
          <li className="border-l border-line-soft px-4 py-3">
            <span className="block font-semibold text-ink">{balanced ? "Balanced" : "Out of balance"}</span>
            <span className="text-ink-faint">Checked by code</span>
          </li>
          <li className="border-l border-line-soft px-4 py-3">
            <span className="block font-semibold text-seal">Approved</span>
            <span className="text-ink-faint">Reviewer of Record</span>
          </li>
        </ol>
      </div>

      {/* The one memorable moment: the reviewer's seal. */}
      <div
        aria-hidden
        className="seal-in absolute -right-6 -bottom-24 hidden size-28 sm:grid place-items-center rounded-full border-[3px] border-seal bg-seal-tint/90 text-center text-seal sm:-right-6"
      >
        <span className="grid size-[92px] place-items-center rounded-full border border-seal/60 px-2 font-display text-[13px] leading-tight font-semibold">
          Approved
          <br />
          by Reviewer
          <br />
          of Record
        </span>
      </div>
    </figure>
  );
}
