import Link from "next/link";
import { Badge, PageHeader } from "@/components/ui";
import type { PlannedInterface } from "@/lib/content";

/** Placeholder for interfaces delivered in later phases. Clearly labelled; not a fake feature. */
export function PlannedInterfacePage({ plan }: { plan: PlannedInterface }) {
  return (
    <>
      <PageHeader
        title={plan.title}
        status={<Badge tone="warn" dot>Not available yet: {plan.phase}</Badge>}
        description="This part of AZINCO is on the roadmap and not built yet. Here is what it will do."
      />
      <ul className="mt-8 grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2">
        {plan.items.map((item) => (
          <li key={item} className="flex gap-3 bg-surface px-5 py-5">
            <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-brand" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
      <p className="mt-8 text-sm text-ink-soft">
        Meanwhile you can{" "}
        <Link href="/account" className="font-medium text-brand hover:underline">
          secure your account with multi-factor authentication
        </Link>
        .
      </p>
    </>
  );
}
