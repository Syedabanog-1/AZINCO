import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

/* Shared UI primitives. Every page uses these so the product looks like one system. */

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white hover:bg-brand-strong",
  secondary: "border border-line bg-surface text-ink hover:border-ink-faint",
  ghost: "text-ink-soft hover:bg-line-soft hover:text-ink",
};
const SIZES: Record<Size, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-3 text-base",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra = "") {
  return `inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${SIZES[size]} ${extra}`;
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ComponentProps<"button"> & { variant?: Variant; size?: Size }) {
  return <button {...props} className={buttonClass(variant, size, className)} />;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant; size?: Size }) {
  return <Link {...props} className={buttonClass(variant, size, className)} />;
}

type Tone = "neutral" | "brand" | "ok" | "fail" | "warn" | "seal";
const TONES: Record<Tone, string> = {
  neutral: "bg-line-soft text-ink-soft",
  brand: "bg-brand-tint text-brand",
  ok: "bg-ok-tint text-ok",
  fail: "bg-fail-tint text-fail",
  warn: "bg-warn-tint text-warn",
  seal: "bg-seal-tint text-seal",
};

export function Badge({ tone = "neutral", dot = false, children }: { tone?: Tone; dot?: boolean; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}>
      {dot ? <span aria-hidden className="size-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  );
}

export function Panel({
  title,
  description,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-line bg-surface ${className}`}>
      {title ? (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line-soft px-5 py-4">
          <div>
            <h2 className="font-sans text-base font-semibold tracking-normal">{title}</h2>
            {description ? <p className="mt-0.5 text-sm text-ink-soft">{description}</p> : null}
          </div>
          {actions}
        </header>
      ) : null}
      <div className="p-5">{children}</div>
    </section>
  );
}

/** Title block at the top of every in-app page. */
export function PageHeader({
  title,
  description,
  actions,
  status,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  status?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
      <div className="max-w-2xl">
        {status ? <div className="mb-3">{status}</div> : null}
        <h1 className="text-3xl sm:text-4xl">{title}</h1>
        {description ? <p className="mt-2 text-ink-soft">{description}</p> : null}
      </div>
      {actions ? <div className="flex gap-2">{actions}</div> : null}
    </div>
  );
}

/** Brand mark: a ledger page with a balancing rule. */
export function Logo({ inverted = false }: { inverted?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden>
        <rect width="28" height="28" rx="6" fill={inverted ? "#ffffff" : "var(--color-brand)"} />
        <path
          d="M8 9h12M8 13h12M8 17h12"
          stroke={inverted ? "var(--color-brand)" : "#ffffff"}
          strokeWidth="1.6"
          strokeLinecap="round"
          opacity="0.55"
        />
        <path d="M8 21h12" stroke={inverted ? "var(--color-brand)" : "#ffffff"} strokeWidth="2" strokeLinecap="round" />
        <path d="M14 6v16" stroke="var(--color-seal)" strokeWidth="1.6" />
      </svg>
      <span className={`font-display text-xl font-semibold tracking-tight ${inverted ? "text-white" : "text-ink"}`}>
        AZINCO
      </span>
    </span>
  );
}
