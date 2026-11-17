import Link from "next/link";
import type { PlannedInterface } from "@/lib/content";

/** Placeholder for interfaces delivered in later steps. Clearly labelled — not a fake feature. */
export function PlannedInterfacePage({ plan }: { plan: PlannedInterface }) {
  return (
    <section className="mx-auto max-w-3xl px-6 py-16">
      <p className="inline-flex rounded-full bg-warn-tint px-3 py-1 text-xs font-semibold text-warn">
        Not available yet · {plan.phase}
      </p>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">{plan.title}</h1>
      <p className="mt-3 text-ink-soft">
        This interface is part of the AZINCO roadmap and is not built yet. Planned capabilities:
      </p>
      <ul className="mt-6 space-y-2">
        {plan.items.map((item) => (
          <li key={item} className="flex gap-3 rounded-md border border-line bg-white px-4 py-3 text-sm">
            <span aria-hidden className="mt-1.5 size-1.5 shrink-0 rounded-full bg-brand" />
            {item}
          </li>
        ))}
      </ul>
      <Link href="/" className="mt-8 inline-block text-sm font-medium text-brand hover:underline">
        ← Back to home
      </Link>
    </section>
  );
}
