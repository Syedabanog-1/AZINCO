"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { buttonClass } from "@/components/ui";
import { apiCall, type Me } from "@/lib/auth/client";

type State = { kind: "loading" } | { kind: "signed-out" } | { kind: "signed-in"; name: string };

/**
 * Header call-to-action that reflects the session: "Sign in" for visitors, "Open workspace" when
 * signed in. Re-checks on every navigation, so it updates right after login and logout.
 */
export function HeaderAuth() {
  const pathname = usePathname();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    void apiCall<Me>("me").then((res) => {
      if (cancelled) return;
      setState(
        res.ok
          ? { kind: "signed-in", name: res.data.display_name || res.data.email }
          : { kind: "signed-out" },
      );
    });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  if (state.kind === "signed-in") {
    return (
      <Link href="/dashboard" className={buttonClass("primary", "md", "ml-2")} title={`Signed in as ${state.name}`}>
        Open workspace
      </Link>
    );
  }
  // While loading, keep the same footprint so the header does not jump.
  return (
    <span className="ml-2 flex items-center gap-1" style={state.kind === "loading" ? { visibility: "hidden" } : undefined}>
      <Link href="/login" className={buttonClass("ghost", "md")} aria-busy={state.kind === "loading"}>
        Sign in
      </Link>
      <Link href="/register" className={buttonClass("primary", "md", "hidden sm:inline-flex")}>
        Get started
      </Link>
    </span>
  );
}
