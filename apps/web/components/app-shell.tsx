"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { Logo } from "@/components/ui";
import { apiCall, type Me } from "@/lib/auth/client";

type NavItem = { href: string; label: string; soon?: boolean };
type NavGroup = { label: string; items: NavItem[]; visible: (me: Me | null) => boolean };

const REVIEW_ROLES = new Set(["reviewer", "second_reviewer"]);

/**
 * Navigation is filtered by role for clarity only. Access is enforced by the API (RBAC + RLS);
 * hiding a link is never a security control.
 */
const GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    visible: () => true,
    items: [
      { href: "/dashboard", label: "Overview", soon: true },
      { href: "/account", label: "Account and security" },
    ],
  },
  {
    label: "Review",
    visible: (me) => !!me?.memberships.some((m) => REVIEW_ROLES.has(m.role)),
    items: [{ href: "/review", label: "Review queue", soon: true }],
  },
  {
    label: "Platform",
    visible: (me) => !!me?.platform_roles.includes("platform_admin"),
    items: [{ href: "/admin", label: "Admin console", soon: true }],
  },
];

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    let cancelled = false;
    void apiCall<Me>("me").then((res) => {
      if (cancelled) return;
      if (res.ok) setMe(res.data);
      else if (res.problem.status === 401) router.replace("/login");
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function signOut() {
    await apiCall<undefined>("auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  const groups = GROUPS.filter((g) => g.visible(me));
  const name = me?.display_name || me?.email || "";

  return (
    <div className="flex flex-1 flex-col lg:flex-row">
      <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-[calc(100dvh-1.85rem)] lg:w-64 lg:shrink-0 lg:flex-col lg:border-r lg:border-b-0">
        <div className="flex items-center justify-between px-5 py-4">
          <Link href="/" aria-label="AZINCO home">
            <Logo />
          </Link>
        </div>

        <nav aria-label="Workspace" className="flex gap-6 overflow-x-auto px-3 pb-3 lg:flex-1 lg:flex-col lg:gap-5 lg:overflow-visible lg:pt-2">
          {groups.map((g) => (
            <div key={g.label} className="shrink-0">
              <h2 className="px-2 font-sans text-xs font-semibold tracking-normal text-ink-faint">{g.label}</h2>
              <ul className="mt-1.5 flex gap-1 lg:flex-col">
                {g.items.map((item) => {
                  const active = pathname === item.href;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={`flex items-center justify-between gap-3 rounded-md px-2 py-2 text-sm whitespace-nowrap ${
                          active
                            ? "bg-brand-tint font-semibold text-brand"
                            : "text-ink-soft hover:bg-line-soft hover:text-ink"
                        }`}
                      >
                        {item.label}
                        {item.soon ? <span className="text-xs font-normal text-ink-faint">Soon</span> : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          <div className="shrink-0 lg:mt-auto">
            <Link href="/status" className="block rounded-md px-2 py-2 text-sm whitespace-nowrap text-ink-soft hover:bg-line-soft hover:text-ink">
              System status
            </Link>
          </div>
        </nav>

        <div className="hidden border-t border-line px-4 py-4 lg:block">
          {me ? (
            <div className="flex items-center gap-3">
              <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-tint text-sm font-semibold text-brand">
                {initials(name)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{name}</p>
                <button onClick={signOut} className="text-xs text-ink-soft hover:text-ink hover:underline">
                  Sign out
                </button>
              </div>
            </div>
          ) : (
            <div className="h-9 animate-pulse rounded-md bg-line-soft" aria-hidden />
          )}
        </div>
      </aside>

      <main id="main" className="min-w-0 flex-1">
        <div className="mx-auto max-w-5xl px-6 py-10 lg:px-10">{children}</div>
      </main>
    </div>
  );
}
