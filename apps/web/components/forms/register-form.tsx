"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import { Alert, Field, SubmitButton } from "@/components/auth-ui";
import { apiCall, messageFor } from "@/lib/auth/client";

export function RegisterForm({ devMailboxUrl }: { devMailboxUrl: string | null }) {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const res = await apiCall<{ message: string }>("auth/register", {
      method: "POST",
      body: { email, password, display_name: displayName },
    });
    setBusy(false);
    if (res.ok) setDone(res.data.message);
    else setError(messageFor(res.problem));
  }

  if (done) {
    return (
      <div className="space-y-4">
        <Alert kind="success">{done}</Alert>
        {devMailboxUrl ? (
          <Alert kind="info">
            [MOCK] Local development: the e-mail is caught by Mailpit. Open{" "}
            <a href={devMailboxUrl} target="_blank" rel="noreferrer" className="font-medium underline">
              the test inbox
            </a>{" "}
            and click the confirmation link.
          </Alert>
        ) : null}
        <Link href="/login" className="block text-center text-sm font-medium text-brand hover:underline">
          Go to sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <Field label="Your name" name="name" autoComplete="name" required maxLength={100}
        value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
      <Field label="E-mail" type="email" name="email" autoComplete="email" required
        value={email} onChange={(e) => setEmail(e.target.value)} />
      <Field label="Password" type="password" name="password" autoComplete="new-password" required
        minLength={12} hint="At least 12 characters. A short sentence is easy to remember."
        value={password} onChange={(e) => setPassword(e.target.value)} />
      <SubmitButton busy={busy}>Create account</SubmitButton>
      <p className="text-center text-sm text-ink-soft">
        Already registered?{" "}
        <Link href="/login" className="font-medium text-brand hover:underline">Sign in</Link>
      </p>
    </form>
  );
}
