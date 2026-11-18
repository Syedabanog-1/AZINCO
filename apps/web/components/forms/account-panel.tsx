"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Alert, Field, SubmitButton } from "@/components/auth-ui";
import { apiCall, type Me, messageFor } from "@/lib/auth/client";

type MfaSetup = { otpauth_uri: string; secret: string; qr_svg: string };

const ROLE_LABELS: Record<string, string> = {
  client_owner: "Client owner",
  client_staff: "Client staff",
  support_ops: "Support / Ops",
  reviewer: "Reviewer of Record",
  second_reviewer: "Second reviewer",
  local_partner: "Local partner",
  auditor: "External auditor",
};

export function AccountPanel() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await apiCall<Me>("me");
    if (res.ok) setMe(res.data);
    else if (res.problem.status === 401) router.replace("/login");
    else setError(messageFor(res.problem));
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  async function startMfa() {
    setBusy(true);
    setError(null);
    const res = await apiCall<MfaSetup>("auth/mfa/setup", { method: "POST" });
    setBusy(false);
    if (res.ok) setSetup(res.data);
    else setError(messageFor(res.problem));
  }

  async function confirmMfa(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const res = await apiCall<undefined>("auth/mfa/confirm", { method: "POST", body: { code } });
    setBusy(false);
    if (res.ok) {
      setSetup(null);
      setCode("");
      setNotice("Multi-factor authentication is now on for your account.");
      await load();
    } else setError(messageFor(res.problem));
  }

  async function logout() {
    await apiCall<undefined>("auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  if (!me) {
    return error ? <Alert kind="error">{error}</Alert> : <div className="h-40 animate-pulse rounded-lg bg-line/50" aria-busy="true" />;
  }

  return (
    <div className="space-y-6">
      {notice ? <Alert kind="success">{notice}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {me.mfa_required && !me.mfa_satisfied ? (
        <Alert kind="error">
          Your role requires multi-factor authentication. Set it up below to continue.
        </Alert>
      ) : null}

      <div className="rounded-lg border border-line bg-surface p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-display text-2xl">{me.display_name}</p>
            <p className="text-sm text-ink-soft">{me.email}</p>
          </div>
          <button onClick={logout} className="rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium hover:border-ink-faint">
            Sign out
          </button>
        </div>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-ink-soft">Account type</dt>
            <dd className="font-medium capitalize">{me.user_type}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Multi-factor authentication</dt>
            <dd className={`font-medium ${me.mfa_enabled ? "text-ok" : "text-warn"}`}>
              {me.mfa_enabled ? "On" : me.mfa_required ? "Required — not set up" : "Off (recommended)"}
            </dd>
          </div>
        </dl>
      </div>

      <div className="rounded-lg border border-line bg-surface p-5">
        <h2 className="font-sans text-base font-semibold tracking-normal">Workspaces</h2>
        {me.memberships.length === 0 ? (
          <p className="mt-2 text-sm text-ink-soft">
            You are not part of a client workspace yet. Business onboarding opens in Phase 1.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {me.memberships.map((m) => (
              <li key={`${m.tenant_id}-${m.role}`} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium">{m.tenant_name}</span>
                <span className="rounded-full bg-brand-tint px-2.5 py-0.5 text-xs font-semibold text-brand">
                  {ROLE_LABELS[m.role] ?? m.role}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {!me.mfa_enabled ? (
        <div className="rounded-lg border border-line bg-surface p-5">
          <h2 className="font-sans text-base font-semibold tracking-normal">Set up multi-factor authentication</h2>
          {!setup ? (
            <>
              <p className="mt-2 text-sm text-ink-soft">
                Use an authenticator app (Google Authenticator, Microsoft Authenticator, Authy, 1Password…).
              </p>
              <button onClick={startMfa} disabled={busy}
                className="mt-4 rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-strong disabled:opacity-60">
                Start setup
              </button>
            </>
          ) : (
            <form onSubmit={confirmMfa} className="mt-4 space-y-4">
              <p className="text-sm text-ink-soft">
                1. On your phone, open an authenticator app (Google Authenticator, Microsoft
                Authenticator or Authy), tap <strong>+</strong> and scan this QR code.
              </p>
              {/* SVG rendered as an image: no scripts can run from it. */}
              <img
                src={`data:image/svg+xml;utf8,${encodeURIComponent(setup.qr_svg)}`}
                alt="QR code for your authenticator app"
                width={200}
                height={200}
                className="rounded-md border border-line bg-surface"
              />
              <p className="text-xs text-ink-soft">
                Can&rsquo;t scan? Choose &ldquo;Enter a setup key&rdquo; in the app and type this key (keep it
                private):{" "}
                <code className="select-all break-all rounded bg-paper px-1.5 py-0.5 font-mono">{setup.secret}</code>
              </p>
              <Field label="2. Enter the 6-digit code" name="code" inputMode="numeric" autoComplete="one-time-code"
                hint="The code the app shows next to AZINCO. It changes every 30 seconds; your phone's time must be set automatically."
                maxLength={6} required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
              <SubmitButton busy={busy}>Turn on MFA</SubmitButton>
            </form>
          )}
        </div>
      ) : null}
    </div>
  );
}
