import Link from "next/link";
import type { ReactNode } from "react";
import { HeaderAuth } from "@/components/header-auth";
import { Logo } from "@/components/ui";

const NAV = [
  { href: "/#services", label: "Services" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#pricing", label: "Payments" },
  { href: "/status", label: "System status" },
] as const;

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3.5">
          <Link href="/" aria-label="AZINCO home">
            <Logo />
          </Link>
          <nav aria-label="Main" className="flex items-center gap-1 text-sm">
            <div className="hidden items-center gap-1 md:flex">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-3 py-2 text-ink-soft hover:bg-line-soft hover:text-ink"
                >
                  {item.label}
                </Link>
              ))}
            </div>
            <HeaderAuth />
          </nav>
        </div>
      </header>
      <main id="main" className="flex-1">
        {children}
      </main>
      <footer className="border-t border-line bg-surface">
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-10 text-sm sm:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <Logo />
            <p className="mt-3 max-w-sm text-ink-soft">
              AI prepares, code calculates, and a qualified Reviewer of Record approves every
              deliverable.
            </p>
          </div>
          <div>
            <h2 className="font-sans text-sm font-semibold tracking-normal">Product</h2>
            <ul className="mt-3 space-y-2 text-ink-soft">
              <li><Link href="/#services" className="hover:text-ink">Services</Link></li>
              <li><Link href="/#how-it-works" className="hover:text-ink">How it works</Link></li>
              <li><Link href="/status" className="hover:text-ink">System status</Link></li>
            </ul>
          </div>
          <div>
            <h2 className="font-sans text-sm font-semibold tracking-normal">Account</h2>
            <ul className="mt-3 space-y-2 text-ink-soft">
              <li><Link href="/login" className="hover:text-ink">Sign in</Link></li>
              <li><Link href="/register" className="hover:text-ink">Create an account</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-line-soft">
          <p className="mx-auto max-w-6xl px-6 py-4 text-xs text-ink-faint">
            © AZINCO. Synthetic data only in this environment.
          </p>
        </div>
      </footer>
    </>
  );
}
