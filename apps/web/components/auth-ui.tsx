import type { InputHTMLAttributes, ReactNode } from "react";
import { useId } from "react";
import { buttonClass } from "@/components/ui";

/** Heading block for the auth pages. The (auth) layout supplies the surrounding frame. */
export function AuthCard({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <h1 className="text-4xl">{title}</h1>
      {subtitle ? <p className="mt-2 text-ink-soft">{subtitle}</p> : null}
      <div className="mt-8">{children}</div>
    </section>
  );
}

export function Field({
  label,
  hint,
  ...input
}: { label: string; hint?: string } & InputHTMLAttributes<HTMLInputElement>) {
  const hintId = useId();
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      <input
        {...input}
        aria-describedby={hint ? hintId : undefined}
        className="mt-1.5 block w-full rounded-md border border-line bg-surface px-3 py-2.5 text-[15px] shadow-[inset_0_1px_0_rgba(21,32,30,0.03)] transition-colors outline-none placeholder:text-ink-faint hover:border-ink-faint focus:border-brand focus:ring-2 focus:ring-brand/15"
      />
      {hint ? (
        <span id={hintId} className="mt-1.5 block text-xs text-ink-soft">
          {hint}
        </span>
      ) : null}
    </label>
  );
}

export function SubmitButton({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <button type="submit" disabled={busy} aria-busy={busy} className={buttonClass("primary", "lg", "w-full")}>
      {busy ? (
        <>
          <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          Please wait
        </>
      ) : (
        children
      )}
    </button>
  );
}

export function Alert({ kind, children }: { kind: "error" | "success" | "info"; children: ReactNode }) {
  const styles = {
    error: "border-fail bg-fail-tint text-fail",
    success: "border-ok bg-ok-tint text-ok",
    info: "border-line bg-paper text-ink-soft",
  }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-md border-l-4 px-4 py-3 text-sm ${styles}`}>
      {children}
    </div>
  );
}
