import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/ui";
import { PRINCIPLES } from "@/lib/content";

/** Sign-in, registration and e-mail confirmation: form on the left, what AZINCO commits to on the right. */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid flex-1 lg:grid-cols-[1fr_minmax(0,34rem)]">
      <div className="flex flex-col px-6 py-8 sm:px-10">
        <Link href="/" aria-label="AZINCO home" className="self-start">
          <Logo />
        </Link>
        <main id="main" className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-sm">{children}</div>
        </main>
      </div>
      <aside className="hidden bg-brand-deep px-12 py-16 text-white lg:flex lg:flex-col lg:justify-center">
        <h2 className="text-3xl text-white">Books you can stand behind</h2>
        <dl className="mt-10 space-y-6">
          {PRINCIPLES.map((p) => (
            <div key={p.title} className="border-l-2 border-seal pl-4">
              <dt className="font-semibold">{p.title}</dt>
              <dd className="mt-1 text-sm text-white/70">{p.body}</dd>
            </div>
          ))}
        </dl>
      </aside>
    </div>
  );
}
