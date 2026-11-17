import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "AZINCO — AI-assisted accounting, expert approved", template: "%s · AZINCO" },
  description:
    "Bookkeeping, reconciliation, financial statements and tax records for Pakistani and international businesses. AI prepares, code calculates, a qualified Reviewer of Record approves.",
};

const NAV = [
  { href: "/", label: "Home" },
  { href: "/#services", label: "Services" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/status", label: "System status" },
] as const;

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <div className="bg-warn-tint text-warn border-b border-line px-4 py-1.5 text-center text-xs font-medium">
          Pre-alpha (Phase 0). Not production-ready. Payments, AI models and OCR are [MOCK] or
          [SANDBOX].
        </div>
        <header className="border-b border-line bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-2" aria-label="AZINCO home">
              <span className="grid size-8 place-items-center rounded-md bg-brand text-sm font-bold text-white">
                AZ
              </span>
              <span className="text-lg font-semibold tracking-tight">AZINCO</span>
            </Link>
            <nav aria-label="Main" className="flex items-center gap-1 text-sm">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-3 py-2 text-ink-soft hover:bg-paper hover:text-ink"
                >
                  {item.label}
                </Link>
              ))}
              <Link
                href="/login"
                className="ml-2 rounded-md bg-brand px-4 py-2 font-medium text-white hover:bg-brand-strong"
              >
                Sign in
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-line bg-white">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 text-xs text-ink-soft sm:flex-row sm:justify-between">
            <p>© AZINCO. AI prepares → code calculates → a qualified Reviewer of Record approves.</p>
            <p>Synthetic data only in this environment.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
