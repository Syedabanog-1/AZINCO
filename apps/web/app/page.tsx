import Link from "next/link";
import {
  DELIVERY_MODES,
  JOURNEY,
  JURISDICTIONS,
  PRINCIPLES,
  SERVICES,
} from "@/lib/content";

export default function HomePage() {
  return (
    <>
      <section className="border-b border-line bg-white">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-20 lg:grid-cols-[1.2fr_1fr] lg:items-center">
          <div>
            <p className="mb-4 inline-flex rounded-full bg-brand-tint px-3 py-1 text-xs font-semibold text-brand">
              Pakistan · United Kingdom · United States · Canada · Australia
            </p>
            <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              AI prepares.
              <br />
              Code calculates.
              <br />
              <span className="text-brand">Experts approve.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-ink-soft">
              Bookkeeping, reconciliation, financial statements and tax-ready records for shops,
              factories, property businesses and corporates — every figure traceable to its source
              document, every deliverable signed off by a qualified Reviewer of Record.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/login"
                className="rounded-md bg-brand px-5 py-3 text-sm font-medium text-white hover:bg-brand-strong"
              >
                Get started
              </Link>
              <Link
                href="#how-it-works"
                className="rounded-md border border-line bg-white px-5 py-3 text-sm font-medium hover:bg-paper"
              >
                See how it works
              </Link>
            </div>
          </div>
          <ul className="grid gap-3" aria-label="Core principles">
            {PRINCIPLES.map((p) => (
              <li key={p.title} className="rounded-lg border border-line bg-paper p-4">
                <p className="text-sm font-semibold">{p.title}</p>
                <p className="mt-1 text-sm text-ink-soft">{p.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="services" className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="text-2xl font-semibold tracking-tight">Services</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SERVICES.map((s) => (
            <article key={s.title} className="rounded-lg border border-line bg-white p-5">
              <h3 className="font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm text-ink-soft">{s.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="border-y border-line bg-white">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
          <ol className="mt-8 grid gap-4 md:grid-cols-5">
            {JOURNEY.map((step, i) => (
              <li key={step.title} className="rounded-lg border border-line p-4">
                <span className="text-xs font-semibold text-brand">Stage {i + 1}</span>
                <p className="mt-1 font-semibold">{step.title}</p>
                <p className="mt-2 text-sm text-ink-soft">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-10 px-6 py-16 lg:grid-cols-2">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Delivery modes</h2>
          <p className="mt-2 text-sm text-ink-soft">
            Chosen per country at onboarding and written into your engagement letter. Filing is
            offered only where licensing and legal authority are verified.
          </p>
          <dl className="mt-6 divide-y divide-line rounded-lg border border-line bg-white">
            {DELIVERY_MODES.map((m) => (
              <div key={m.code} className="flex gap-4 p-4">
                <dt className="grid size-8 shrink-0 place-items-center rounded-md bg-brand-tint font-semibold text-brand">
                  {m.code}
                </dt>
                <dd>
                  <p className="font-medium">{m.title}</p>
                  <p className="text-sm text-ink-soft">{m.body}</p>
                </dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="flex flex-col gap-6">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Payments</h2>
            <p className="mt-2 text-sm text-ink-soft">
              An advance starts your task; final deliverables unlock when the balance is settled.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-line bg-white p-4">
                <p className="font-medium">Banking Channels</p>
                <p className="mt-1 text-sm text-ink-soft">Domestic payments within Pakistan.</p>
              </div>
              <div className="rounded-lg border border-line bg-white p-4">
                <p className="font-medium">Card / PayPal</p>
                <p className="mt-1 text-sm text-ink-soft">International clients.</p>
              </div>
            </div>
            <p className="mt-3 text-xs text-ink-soft">
              &ldquo;In Escrow (Work Active)&rdquo; is a task status: your advance is committed to
              your task and held in AZINCO&rsquo;s operating account, not a segregated escrow
              account.
            </p>
          </div>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Jurisdictions</h2>
            <ul className="mt-4 flex flex-wrap gap-2">
              {JURISDICTIONS.map((j) => (
                <li
                  key={j}
                  className="rounded-full border border-line bg-white px-3 py-1 text-sm"
                >
                  {j}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-ink-soft">
              Country rule packs are being prepared from official sources and approved by the
              Reviewer of Record before use. No tax rate is applied until its rule pack is active.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
