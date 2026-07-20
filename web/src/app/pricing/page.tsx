import Link from "next/link";
import { pricing as copy, site } from "@/lib/copy";
import {
  fetchPricingCatalog,
  formatMoney,
  formatOverage,
  formatPlanPrice,
  type Plan,
} from "@/lib/api";

const OPS =
  process.env.NEXT_PUBLIC_OPS_URL?.replace(/\/$/, "") ||
  "http://localhost:3001";

export const metadata = {
  title: `Pricing | ${site.brand}`,
  description: copy.supporting,
};

function SiteHeader() {
  return (
    <header className="animate-fade relative z-[1] mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 pt-8 sm:px-10 lg:px-12">
      <p className="font-display text-2xl font-semibold tracking-[-0.03em] text-[#f3f8f5] sm:text-3xl">
        <Link href="/" className="text-inherit no-underline">
          {copy.brand}
        </Link>
      </p>
      <nav aria-label="Primary">
        <ul className="m-0 flex list-none items-center gap-5 p-0">
          <li>
            <Link
              href="/signup?plan=growth"
              className="text-sm font-medium text-[#afc2ba] transition-colors hover:text-[#f3f8f5]"
            >
              Sign up
            </Link>
          </li>
          <li>
            <a
              href={`${OPS}/login`}
              className="text-sm font-medium text-[#afc2ba] transition-colors hover:text-[#f3f8f5]"
            >
              Sign in
            </a>
          </li>
        </ul>
      </nav>
    </header>
  );
}

function PlanColumn({ plan, index }: { plan: Plan; index: number }) {
  const href = `/signup?plan=${encodeURIComponent(plan.key)}`;
  const minutes = plan.entitlements?.monthly_minutes;
  const concurrent = plan.entitlements?.concurrent_calls;
  const numbers = plan.entitlements?.phone_numbers;
  const delayClass =
    index === 0
      ? "animate-rise"
      : index === 1
        ? "animate-rise-delay"
        : "animate-rise-delay-2";

  return (
    <li
      className={`relative flex min-w-0 flex-col ${delayClass} ${
        plan.popular ? "lg:-mt-4 lg:mb-0" : ""
      }`}
    >
      {plan.popular && plan.badge ? (
        <p className="m-0 mb-3 font-mono text-[11px] tracking-[0.16em] text-teal uppercase">
          {plan.badge}
        </p>
      ) : (
        <p className="mb-3 hidden font-mono text-[11px] tracking-[0.16em] text-transparent uppercase lg:block">
          &nbsp;
        </p>
      )}

      <div
        className={
          plan.popular
            ? "flex flex-1 flex-col border-t-2 border-teal pt-6"
            : "flex flex-1 flex-col border-t border-line pt-6"
        }
      >
        <p className="m-0 font-mono text-xs tracking-[0.14em] text-teal uppercase">
          {plan.name}
        </p>

        <p className="mt-4 m-0 font-display text-[clamp(2.4rem,4vw,3.25rem)] font-semibold leading-none tracking-[-0.04em] text-ink">
          {formatPlanPrice(plan)}
          <span className="ml-1.5 align-baseline text-base font-sans font-medium tracking-normal text-muted">
            /mo
          </span>
        </p>

        {plan.annual_amount != null ? (
          <p className="mt-2 m-0 text-sm text-muted">
            {formatMoney(plan.annual_amount, plan.currency || "usd")} billed yearly
          </p>
        ) : null}

        <p className="mt-4 m-0 max-w-[18rem] text-base leading-relaxed text-muted">
          {plan.tagline}
        </p>

        <dl className="mt-8 m-0 grid gap-3 border-t border-line pt-6">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-sm text-muted">Voice minutes</dt>
            <dd className="m-0 font-display text-xl font-semibold tracking-[-0.02em] text-ink">
              {minutes?.toLocaleString() ?? "—"}
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-sm text-muted">Concurrent calls</dt>
            <dd className="m-0 font-display text-xl font-semibold tracking-[-0.02em] text-ink">
              {concurrent ?? "—"}
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-sm text-muted">Phone numbers</dt>
            <dd className="m-0 font-display text-xl font-semibold tracking-[-0.02em] text-ink">
              {numbers ?? "—"}
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-sm text-muted">Overage</dt>
            <dd className="m-0 text-sm font-semibold text-ink">
              {formatOverage(plan.overage_per_minute_cents)}
            </dd>
          </div>
        </dl>

        <ul className="mt-8 m-0 flex flex-1 list-none flex-col gap-2.5 p-0">
          {(plan.highlights ?? plan.features.slice(0, 5)).map((item) => (
            <li key={item} className="text-sm leading-snug text-ink-soft">
              {item}
            </li>
          ))}
        </ul>

        <Link
          href={href}
          className={
            plan.popular
              ? "mt-10 inline-flex items-center justify-center rounded-md bg-[#45d6ac] px-5 py-3 text-sm font-semibold text-[#07120f] transition-[transform,background-color] duration-200 hover:translate-y-[-1px] hover:bg-[#71f0ca]"
              : "mt-10 inline-flex items-center justify-center rounded-md border border-line bg-transparent px-5 py-3 text-sm font-semibold text-ink transition-colors duration-200 hover:border-teal hover:text-teal-deep"
          }
        >
          {plan.cta || `Choose ${plan.name}`}
        </Link>
      </div>
    </li>
  );
}

export default async function PricingPage() {
  let catalog: Awaited<ReturnType<typeof fetchPricingCatalog>> | null = null;
  let loadError: string | null = null;
  try {
    catalog = await fetchPricingCatalog(true);
  } catch {
    loadError = "Plans are temporarily unavailable. Try again shortly.";
  }

  const plans = catalog?.plans ?? [];
  const enterprise = catalog?.enterprise;
  const trial = catalog?.trial;
  const numberPricing = catalog?.number_pricing;
  const addOns = catalog?.add_ons ?? [];

  return (
    <main id="main-content">
      <section
        className="relative isolate min-h-[70svh] overflow-hidden"
        aria-labelledby="pricing-hero-heading"
      >
        <div className="hero-stage" aria-hidden="true">
          <div className="hero-glow" />
          <div
            className="ring"
            style={{ width: "min(36vw, 280px)", height: "min(36vw, 280px)" }}
          />
          <div
            className="ring ring-2"
            style={{ width: "min(36vw, 280px)", height: "min(36vw, 280px)" }}
          />
        </div>

        <div className="relative z-[1] mx-auto flex min-h-[70svh] w-full max-w-6xl flex-col px-6 pb-16 sm:px-10 lg:px-12">
          <SiteHeader />

          <div className="flex flex-1 flex-col justify-end gap-6 pb-4 pt-20 sm:max-w-xl sm:justify-center sm:pb-8 lg:max-w-2xl">
            <h1
              id="pricing-hero-heading"
              className="animate-rise font-display m-0 text-[clamp(2.5rem,7vw,4.25rem)] font-semibold leading-[0.98] tracking-[-0.035em] text-[#f3f8f5]"
            >
              {copy.title}
            </h1>
            <p className="animate-rise-delay m-0 max-w-md text-base leading-relaxed text-[#afc2ba] sm:text-lg">
              {copy.supporting}
            </p>
            <div className="animate-rise-delay-2 flex flex-wrap items-center gap-3">
              <Link
                href="/signup?plan=growth"
                className="inline-flex items-center justify-center rounded-md bg-[#45d6ac] px-5 py-3 text-sm font-semibold text-[#07120f] transition-[transform,background-color] duration-200 hover:translate-y-[-1px] hover:bg-[#71f0ca]"
              >
                {copy.primaryCta}
              </Link>
              <a
                href="#plans"
                className="inline-flex items-center justify-center rounded-md border border-[rgba(185,225,210,0.28)] px-5 py-3 text-sm font-semibold text-[#f3f8f5] transition-colors hover:border-[#45d6ac]/70"
              >
                Compare plans
              </a>
            </div>
          </div>
        </div>
      </section>

      <section
        id="plans"
        className="section-band px-6 py-20 sm:px-10 lg:px-12"
        aria-labelledby="plans-heading"
      >
        <div className="mx-auto max-w-6xl">
          <h2
            id="plans-heading"
            className="font-display m-0 text-[clamp(1.75rem,3vw,2.5rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink"
          >
            Three plans. One pricing logic.
          </h2>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted">
            Included minutes and concurrency set the base. Dispatch and tech
            mobile unlock on Growth and above.
          </p>

          {loadError ? (
            <p className="mt-10 text-sm text-muted" role="alert">
              {loadError}
            </p>
          ) : (
            <ul className="mt-14 m-0 grid list-none gap-12 p-0 lg:grid-cols-3 lg:gap-10">
              {plans.map((plan, index) => (
                <PlanColumn key={plan.key} plan={plan} index={index} />
              ))}
            </ul>
          )}
        </div>
      </section>

      {plans.length > 0 && !loadError ? (
        <section
          className="border-t border-line bg-paper px-6 py-16 sm:px-10 lg:px-12"
          aria-labelledby="glance-heading"
        >
          <div className="mx-auto max-w-6xl">
            <h2
              id="glance-heading"
              className="font-display m-0 text-[clamp(1.75rem,3vw,2.25rem)] font-semibold tracking-[-0.03em] text-ink"
            >
              {copy.comparisonTitle}
            </h2>
            <div className="mt-10 grid gap-8 sm:grid-cols-3">
              {plans.map((plan) => (
                <div key={plan.key} className="border-t border-line pt-5">
                  <p className="m-0 font-mono text-xs tracking-[0.14em] text-teal uppercase">
                    {plan.name}
                  </p>
                  <ul className="mt-4 m-0 list-none space-y-2 p-0 text-sm text-ink-soft">
                    <li>
                      {plan.entitlements?.team_users ?? "—"} team users
                    </li>
                    <li>
                      {plan.entitlements?.knowledge_documents ?? "—"} knowledge
                      docs
                    </li>
                    <li>
                      Dispatch:{" "}
                      {plan.entitlements?.dispatch_enabled ? "Yes" : "No"}
                    </li>
                    <li>
                      Tech mobile:{" "}
                      {plan.entitlements?.tech_mobile_enabled ? "Yes" : "No"}
                    </li>
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {enterprise ? (
        <section
          className="relative overflow-hidden bg-ink px-6 py-24 text-[#f3f8f5] sm:px-10 lg:px-12"
          aria-labelledby="enterprise-heading"
        >
          <div
            className="pointer-events-none absolute inset-0 opacity-70"
            aria-hidden="true"
            style={{
              background:
                "radial-gradient(70% 60% at 50% 0%, rgba(26,168,132,0.28), transparent 60%)",
            }}
          />
          <div className="relative z-[1] mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div>
              <p className="m-0 font-mono text-xs tracking-[0.14em] text-[#71f0ca] uppercase">
                {enterprise.name}
              </p>
              <h2
                id="enterprise-heading"
                className="font-display mt-3 m-0 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em]"
              >
                High volume. Custom limits.
              </h2>
              <p className="mt-4 m-0 max-w-lg text-base leading-relaxed text-[#afc2ba]">
                {enterprise.tagline}
              </p>
              <ul className="mt-8 m-0 grid list-none gap-2 p-0 sm:grid-cols-2">
                {(enterprise.highlights ?? enterprise.features.slice(0, 6)).map(
                  (item) => (
                    <li key={item} className="text-sm text-[#d5e6df]">
                      {item}
                    </li>
                  ),
                )}
              </ul>
            </div>
            <div>
              <a
                href={copy.contactSalesHref}
                className="inline-flex items-center justify-center rounded-md bg-[#45d6ac] px-5 py-3 text-sm font-semibold text-[#07120f] transition-[transform,background-color] duration-200 hover:translate-y-[-1px] hover:bg-[#71f0ca]"
              >
                {enterprise.cta}
              </a>
            </div>
          </div>
        </section>
      ) : null}

      {trial ? (
        <section
          className="border-t border-line bg-fog px-6 py-20 sm:px-10 lg:px-12"
          aria-labelledby="trial-heading"
        >
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1fr_1fr] lg:items-end">
            <div>
              <h2
                id="trial-heading"
                className="font-display m-0 text-[clamp(1.75rem,3vw,2.5rem)] font-semibold tracking-[-0.03em] text-ink"
              >
                {copy.trialTitle}
              </h2>
              <p className="mt-4 m-0 max-w-md text-base leading-relaxed text-muted">
                {trial.summary}
              </p>
            </div>
            <div>
              <p className="m-0 text-sm font-medium text-ink">
                Phone numbers need a verified account
              </p>
              <ul className="mt-3 m-0 grid list-none gap-2 p-0">
                {trial.phone_number_requirements.map((item) => (
                  <li key={item} className="text-sm text-muted">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      ) : null}

      {numberPricing ? (
        <section
          className="border-t border-line bg-paper px-6 py-20 sm:px-10 lg:px-12"
          aria-labelledby="numbers-heading"
        >
          <div className="mx-auto max-w-6xl">
            <h2
              id="numbers-heading"
              className="font-display m-0 text-[clamp(1.75rem,3vw,2.5rem)] font-semibold tracking-[-0.03em] text-ink"
            >
              {copy.numbersTitle}
            </h2>
            <div className="mt-12 grid gap-12 sm:grid-cols-2">
              <div className="border-t border-line pt-6">
                <h3 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                  Connect your Twilio number
                </h3>
                <p className="mt-3 m-0 text-base leading-relaxed text-muted">
                  {numberPricing.connect_existing.summary}
                </p>
              </div>
              <div className="border-t border-line pt-6">
                <h3 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                  Buy through Call Bot
                </h3>
                <p className="mt-3 m-0 font-display text-3xl font-semibold tracking-[-0.03em] text-ink">
                  {formatMoney(
                    numberPricing.platform_purchase.us_local_monthly_cents,
                  )}
                  <span className="ml-1 text-base font-sans font-medium text-muted">
                    /mo US local
                  </span>
                </p>
                <p className="mt-3 m-0 text-base leading-relaxed text-muted">
                  {numberPricing.platform_purchase.summary}
                </p>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {addOns.length > 0 ? (
        <section
          className="border-t border-line bg-fog px-6 py-20 sm:px-10 lg:px-12"
          aria-labelledby="addons-heading"
        >
          <div className="mx-auto max-w-6xl">
            <h2
              id="addons-heading"
              className="font-display m-0 text-[clamp(1.75rem,3vw,2.5rem)] font-semibold tracking-[-0.03em] text-ink"
            >
              {copy.addOnsTitle}
            </h2>
            <p className="mt-3 max-w-lg text-base text-muted">
              Per-user and capacity extras stay optional — the plan carries the
              voice load.
            </p>
            <ul className="mt-12 m-0 grid list-none gap-x-10 gap-y-8 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {addOns.map((addon) => (
                <li key={addon.key} className="border-t border-line pt-5">
                  <p className="m-0 text-base font-semibold text-ink">
                    {addon.name}
                  </p>
                  <p className="mt-2 m-0 font-display text-2xl font-semibold tracking-[-0.02em] text-ink">
                    {addon.unit_amount != null
                      ? formatMoney(addon.unit_amount, addon.currency)
                      : addon.summary || "Quoted"}
                    {addon.unit_amount != null && addon.interval === "month" ? (
                      <span className="ml-1 text-sm font-sans font-medium text-muted">
                        /mo
                      </span>
                    ) : null}
                    {addon.unit_amount != null &&
                    addon.interval === "one_time" ? (
                      <span className="ml-1 text-sm font-sans font-medium text-muted">
                        once
                      </span>
                    ) : null}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      <footer className="border-t border-line bg-paper px-6 py-12 sm:px-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-display m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
              {site.brand}
            </p>
            <p className="mt-2 m-0 max-w-md text-sm leading-relaxed text-muted">
              {copy.annualNote}
            </p>
            <p className="mt-2 m-0 max-w-md text-sm leading-relaxed text-muted">
              {copy.note}
            </p>
          </div>
          <Link
            href="/signup?plan=growth"
            className="inline-flex items-center justify-center rounded-md bg-teal px-5 py-3 text-sm font-semibold text-[#f3f8f5] transition-colors hover:bg-teal-deep"
          >
            {copy.primaryCta}
          </Link>
        </div>
      </footer>
    </main>
  );
}
