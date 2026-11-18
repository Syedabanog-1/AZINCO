"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { apiCall, type Me } from "@/lib/auth/client";

type State = { kind: "loading" } | { kind: "signed-out" } | { kind: "signed-in"; name: string };

const BUTTON =
  "ml-2 rounded-md bg-brand px-4 py-2 font-medium text-white hover:bg-brand-strong";

/**
 * Header call-to-action that reflects the session: "Sign in" for visitors, "My account" when
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
      <Link href="/account" className={BUTTON} title={`Signed in as ${state.name}`}>
        My account
      </Link>
    );
  }
  // While loading, keep the same footprint so the header does not jump.
  return (
    <Link
      href="/login"
      className={BUTTON}
      aria-busy={state.kind === "loading"}
      style={state.kind === "loading" ? { visibility: "hidden" } : undefined}
    >
      Sign in
    </Link>
  );
}
