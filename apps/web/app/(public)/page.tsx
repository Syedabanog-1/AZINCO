import { LedgerEntry } from "@/components/ledger-entry";
import { ButtonLink } from "@/components/ui";
import {
  DELIVERY_MODES,
  JOURNEY,
  JURISDICTIONS,
  PRINCIPLES,
  REPORTING_CURRENCIES,
  SERVICES,
} from "@/lib/content";

export default function HomePage() {
  return (
    <>
      {/* Hero: the promise on the left, the proof (a balanced, approved entry) on the right. */}
      <section className="border-b border-line">
        <div className="mx-auto grid max-w-6xl gap-14 px-6 pt-16 pb-20 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:pt-24">
          <div>
            <h1 className="text-5xl leading-[1.05] sm:text-6xl">
              AI prepares.
              <br />
              Code calculates.
              <br />
              Experts approve.
            </h1>
            <p className="mt-6 max-w-xl text-lg text-ink-soft">
              Bookkeeping, reconciliation, financial statements and tax-ready records for shops,
              factories, property businesses and corporates. Every figure traces back to its source
              document, and every deliverable is signed off by a qualified Reviewer of Record.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink href="/register" size="lg">
                Create an account
              </ButtonLink>
              <ButtonLink href="#how-it-works" size="lg" variant="secondary">
                See how it works
              </ButtonLink>
            </div>
            <p className="mt-8 text-sm text-ink-faint">
              For businesses in {JURISDICTIONS.slice(0, -1).join(", ")} and{" "}
              {JURISDICTIONS[JURISDICTIONS.length - 1]}.
            </p>
          </div>
          <div className="pb-24 lg:pl-6">
            <LedgerEntry />
          </div>
        </div>
      </section>

      {/* Principles: four commitments, set as a ruled list rather than cards. */}
      <section aria-labelledby="principles" className="bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <h2 id="principles" className="text-3xl">
            What you can rely on
          </h2>
          <dl className="mt-8 grid border-t border-ink sm:grid-cols-2">
            {PRINCIPLES.map((p, i) => (
              <div
                key={p.title}
                className={`border-b border-line py-6 sm:pr-10 ${i % 2 === 1 ? "sm:border-l sm:pl-10" : ""}`}
              >
                <dt className="font-semibold">{p.title}</dt>
                <dd className="mt-1.5 text-ink-soft">{p.body}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section id="services" aria-labelledby="services-title" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-20">
        <div className="grid gap-10 lg:grid-cols-[1fr_2fr]">
          <div>
            <h2 id="services-title" className="text-3xl">
              Services
            </h2>
            <p className="mt-3 text-ink-soft">
              Pick what your business needs. Each service is prepared as a draft and reviewed before
              it reaches you.
            </p>
          </div>
          <ul className="grid gap-x-10 sm:grid-cols-2">
            {SERVICES.map((s) => (
              <li key={s.title} className="border-t border-line py-5">
                <h3 className="font-sans text-base font-semibold tracking-normal">{s.title}</h3>
                <p className="mt-1.5 text-sm text-ink-soft">{s.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* A real sequence, so numbered steps are meaningful here. */}
      <section id="how-it-works" aria-labelledby="how-title" className="scroll-mt-20 bg-brand-deep text-white">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <h2 id="how-title" className="text-3xl text-white">
            How it works
          </h2>
          <p className="mt-3 max-w-xl text-white/70">
            Five stages, the same for every engagement. Nothing reaches you until a qualified
            reviewer has approved it.
          </p>
          <ol className="mt-12 grid gap-8 md:grid-cols-5 md:gap-0">
            {JOURNEY.map((step, i) => (
              <li key={step.title} className="relative md:pr-6">
                <div className="flex items-center gap-3">
                  <span
                    className={`figures grid size-9 shrink-0 place-items-center rounded-full border font-display text-lg ${
                      i === 3 ? "border-seal bg-seal text-white" : "border-white/40"
                    }`}
                  >
                    {i + 1}
                  </span>
                  {i < JOURNEY.length - 1 ? (
                    <span aria-hidden className="hidden h-px flex-1 bg-white/25 md:block" />
                  ) : null}
                </div>
                <p className="mt-4 font-semibold">{step.title}</p>
                <p className="mt-1.5 text-sm text-white/70">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-16 px-6 py-20 lg:grid-cols-2">
        <div>
          <h2 className="text-3xl">Delivery modes</h2>
          <p className="mt-3 text-ink-soft">
            Chosen per country at onboarding and written into your engagement letter. Filing is
            offered only where licensing and legal authority are verified.
          </p>
          <dl className="mt-8 border-t border-ink">
            {DELIVERY_MODES.map((m) => (
              <div key={m.code} className="grid grid-cols-[2.5rem_1fr] gap-4 border-b border-line py-4">
                <dt className="font-display text-2xl leading-none text-brand">{m.code}</dt>
                <dd>
                  <p className="font-semibold">{m.title}</p>
                  <p className="mt-0.5 text-sm text-ink-soft">{m.body}</p>
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div id="pricing" className="scroll-mt-20">
          <h2 className="text-3xl">Payments</h2>
          <p className="mt-3 text-ink-soft">
            An advance starts your task; final deliverables unlock when the balance is settled.
            Every amount is recorded in your currency and reported in{" "}
            {REPORTING_CURRENCIES.join(" and ")} at the exchange rate of the payment date.
          </p>
          <dl className="mt-8 border-t border-ink">
            <div className="border-b border-line py-4">
              <dt className="font-semibold">Banking Channels</dt>
              <dd className="mt-0.5 text-sm text-ink-soft">Domestic payments within Pakistan.</dd>
            </div>
            <div className="border-b border-line py-4">
              <dt className="font-semibold">Card</dt>
              <dd className="mt-0.5 text-sm text-ink-soft">
                International clients. Secure card payments processed by Stripe.
              </dd>
            </div>
          </dl>
          <p className="mt-4 rounded-md bg-line-soft px-4 py-3 text-sm text-ink-soft">
            &ldquo;In Escrow (Work Active)&rdquo; is a task status: your advance is committed to your
            task and held in AZINCO&rsquo;s operating account, not a segregated escrow account.
          </p>
          <p className="mt-6 text-sm text-ink-soft">
            Country rule packs are prepared from official sources and approved by the Reviewer of
            Record before use. No tax rate is applied until its rule pack is active.
          </p>
        </div>
      </section>

      <section className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-6 px-6 py-14">
          <div>
            <h2 className="text-3xl">Start with your books</h2>
            <p className="mt-2 text-ink-soft">Create an account, then set up your business profile.</p>
          </div>
          <ButtonLink href="/register" size="lg">
            Create an account
          </ButtonLink>
        </div>
      </section>
    </>
  );
}
