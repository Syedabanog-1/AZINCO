"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { Alert, Field, SubmitButton } from "@/components/auth-ui";
import { apiCall, type Me, messageFor } from "@/lib/auth/client";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needCode, setNeedCode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const res = await apiCall<Me>("auth/login", {
      method: "POST",
      body: { email, password, code: needCode ? code : null },
    });
    setBusy(false);
    if (res.ok) {
      router.push("/account");
      router.refresh();
      return;
    }
    if (res.problem.code === "mfa_code_required") {
      setNeedCode(true);
      setError(needCode ? messageFor(res.problem) : null);
      return;
    }
    setError(messageFor(res.problem));
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <Field label="E-mail" type="email" name="email" autoComplete="username" required
        value={email} onChange={(e) => setEmail(e.target.value)} />
      <Field label="Password" type="password" name="password" autoComplete="current-password" required
        value={password} onChange={(e) => setPassword(e.target.value)} />
      {needCode ? (
        <Field label="Authenticator code" name="code" inputMode="numeric" autoComplete="one-time-code"
          maxLength={6} required autoFocus hint="6-digit code from your authenticator app."
          value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
      ) : null}
      <SubmitButton busy={busy}>Sign in</SubmitButton>
      <p className="text-center text-sm text-ink-soft">
        New to AZINCO?{" "}
        <Link href="/register" className="font-medium text-brand hover:underline">Create an account</Link>
      </p>
    </form>
  );
}
