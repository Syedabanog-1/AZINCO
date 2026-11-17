"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Alert } from "@/components/auth-ui";
import { apiCall, messageFor } from "@/lib/auth/client";

export function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const started = useRef(false);
  const [state, setState] = useState<{ kind: "info" | "success" | "error"; text: string }>({
    kind: "info",
    text: "Confirming your e-mail…",
  });

  useEffect(() => {
    if (started.current) return; // tokens are single-use: never submit twice
    started.current = true;
    if (!token) {
      setState({ kind: "error", text: "This link is missing its token." });
      return;
    }
    void apiCall<{ message: string }>("auth/verify-email", { method: "POST", body: { token } }).then(
      (res) =>
        setState(res.ok ? { kind: "success", text: res.data.message } : { kind: "error", text: messageFor(res.problem) }),
    );
  }, [token]);

  return (
    <div className="space-y-4">
      <Alert kind={state.kind}>{state.text}</Alert>
      {state.kind !== "info" ? (
        <Link href="/login" className="block text-center text-sm font-medium text-brand hover:underline">
          Go to sign in
        </Link>
      ) : null}
    </div>
  );
}
