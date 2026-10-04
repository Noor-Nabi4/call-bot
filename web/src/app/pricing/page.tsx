import Link from "next/link";
import {
  CtaBand,
  Faq,
  JsonLd,
  MarketingShell,
  PageHero,
  RelatedLinks,
  Reveal,
  SectionHeader,
} from "@/components/landing";
import { pricing as pricingCopy } from "@/lib/copy";
import {
  fetchPricingCatalog,
  formatMoney,
  formatOverage,
  formatPlanPrice,
  type PricingCatalog,
} from "@/lib/marketing-api";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildPageMetadata,
  buildProductOfferJsonLd,
  buildWebPageJsonLd,
} from "@/lib/metadata";

export const metadata = buildPageMetadata({
  title: "AI Voice Agent & AI Receptionist Pricing",
  description:
    "AI voice agent pricing based on included minutes, concurrent calls, phone numbers, users, and knowledge documents. See Starter, Growth, Pro, and Enterprise plans.",
  path: "/pricing",
  keywords: [
    "AI voice agent pricing",
    "AI receptionist pricing",
    "AI phone agent pricing",
  ],
});

const pricingFaqs = [
  {
    question: "How much does an AI receptionist cost?",
    answer:
      "Call & Flow Starter, Growth, and Pro plans are priced monthly based on included voice minutes and operational limits. Enterprise is custom. See the plan cards on this page for current list prices.",
  },
  {
    question: "What are overage charges?",
    answer:
      "When you exceed included monthly voice minutes, overage is billed per minute at the rate shown for your plan.",
  },
  {
    question: "Is there a free trial?",
    answer:
      "Yes. The trial includes browser voice testing with a limited minute allotment. Phone number connection has verification and payment requirements described below.",
  },
  {
    question: "Do plans include phone numbers?",
    answer:
      "Each plan includes a phone number allowance. You can connect an existing number or purchase a US local number through the platform where available.",
  },
] as const;

async function loadCatalog(): Promise<PricingCatalog | null> {
  try {
    return await fetchPricingCatalog(true);
  } catch {
    return null;
  }
}

export default async function PricingPage() {
  const catalog = await loadCatalog();
  const plans = catalog
    ? [...catalog.plans, catalog.enterprise]
    : [];

  return (
    <>
      <JsonLd
        data={buildWebPageJsonLd({
          path: "/pricing",
          name: "AI Voice Agent & AI Receptionist Pricing",
          description:
            "AI voice agent pricing based on included minutes, concurrent calls, phone numbers, users, and knowledge documents.",
        })}
      />
      <JsonLd
        data={buildBreadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Pricing", path: "/pricing" },
        ])}
      />
      <JsonLd data={buildFaqJsonLd(pricingFaqs)} />
      {catalog ? (
        <JsonLd
          data={buildProductOfferJsonLd({
            name: "Call & Flow AI Voice Agents",
            description: pricingCopy.supporting,
            path: "/pricing",
            offers: plans.map((plan) => ({
              name: plan.name,
              price: plan.unit_amount,
              priceCurrency: plan.currency || "USD",
              description: plan.tagline,
            })),
          })}
        />
      ) : null}

      <MarketingShell>
        <PageHero
          eyebrow="Pricing"
          title={pricingCopy.title}
          supporting={pricingCopy.supporting}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "Pricing" },
          ]}
          primaryCta={{ href: "/signup", label: "Start Free Trial" }}
          secondaryCta={{ href: "/#demo", label: "Try Voice Demo" }}
        />

        <section
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="plans-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Plans"
                title="Choose the plan that matches your call volume"
                supporting={pricingCopy.note}
                id="plans-heading"
              />
            </Reveal>

            {plans.length === 0 ? (
              <div className="mt-10 rounded-[var(--radius-lg)] border border-line bg-bg p-8">
                <p className="m-0 text-base text-muted">
                  Live plan details load from the billing API. If you are
                  browsing locally without the platform API, start a trial or
                  contact sales for current pricing.
                </p>
                <div className="mt-6 flex flex-wrap gap-3">
                  <Link
                    href="/signup"
                    className="text-sm font-semibold text-teal hover:text-teal-deep"
                  >
                    Start free trial →
                  </Link>
                  <a
                    href={pricingCopy.contactSalesHref}
                    className="text-sm font-semibold text-teal hover:text-teal-deep"
                  >
                    Contact sales →
                  </a>
                </div>
              </div>
            ) : (
              <ul className="mt-10 m-0 grid list-none gap-4 p-0 lg:grid-cols-2 xl:grid-cols-4">
                {plans.map((plan, index) => {
                  const entitlements = plan.entitlements;
                  return (
                    <Reveal
                      key={plan.key}
                      as="li"
                      delay={(index % 3) as 0 | 1 | 2 | 3}
                      variant="scale"
                    >
                      <article
                        className={`flex h-full flex-col rounded-[var(--radius-xl)] border p-6 ${
                          plan.popular
                            ? "border-teal bg-bg shadow-[var(--shadow-md)]"
                            : "border-line bg-bg"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <h2 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                            {plan.name}
                          </h2>
                          {plan.popular || plan.badge ? (
                            <span className="rounded-full bg-teal-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.08em] text-teal-deep uppercase">
                              {plan.badge || "Popular"}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-3 m-0 text-sm text-muted">{plan.tagline}</p>
                        <p className="mt-5 m-0 flex items-baseline gap-2">
                          <span className="font-display text-3xl font-semibold tracking-[-0.04em] text-ink">
                            {formatPlanPrice(plan)}
                          </span>
                          {plan.unit_amount != null ? (
                            <span className="text-sm text-muted">/ month</span>
                          ) : null}
                        </p>
                        {plan.overage_per_minute_cents != null ? (
                          <p className="mt-2 m-0 text-sm text-muted">
                            Overage {formatOverage(plan.overage_per_minute_cents)}
                          </p>
                        ) : null}

                        <ul className="mt-6 m-0 flex list-none flex-col gap-2 p-0">
                          {(plan.highlights || plan.features.slice(0, 5)).map(
                            (feature) => (
                              <li
                                key={feature}
                                className="text-sm leading-snug text-ink-soft"
                              >
                                {feature}
                              </li>
                            ),
                          )}
                        </ul>

                        {entitlements ? (
                          <dl className="mt-6 grid grid-cols-2 gap-3 border-t border-line pt-5 text-xs text-muted">
                            <div>
                              <dt className="m-0">Minutes</dt>
                              <dd className="m-0 mt-1 font-semibold text-ink">
                                {entitlements.monthly_minutes.toLocaleString()}
                              </dd>
                            </div>
                            <div>
                              <dt className="m-0">Concurrent</dt>
                              <dd className="m-0 mt-1 font-semibold text-ink">
                                {entitlements.concurrent_calls}
                              </dd>
                            </div>
                            <div>
                              <dt className="m-0">Numbers</dt>
                              <dd className="m-0 mt-1 font-semibold text-ink">
                                {entitlements.phone_numbers}
                              </dd>
                            </div>
                            <div>
                              <dt className="m-0">Users</dt>
                              <dd className="m-0 mt-1 font-semibold text-ink">
                                {entitlements.team_users}
                              </dd>
                            </div>
                            <div className="col-span-2">
                              <dt className="m-0">Knowledge docs</dt>
                              <dd className="m-0 mt-1 font-semibold text-ink">
                                {entitlements.knowledge_documents}
                              </dd>
                            </div>
                          </dl>
                        ) : null}

                        <div className="mt-auto pt-6">
                          <Link
                            href={
                              plan.checkoutable === false
                                ? pricingCopy.contactSalesHref
                                : `/signup?plan=${encodeURIComponent(plan.key)}`
                            }
                            className={`inline-flex w-full items-center justify-center rounded-[var(--radius-md)] px-4 py-3 text-sm font-semibold no-underline ${
                              plan.popular
                                ? "bg-teal text-white hover:bg-teal-bright"
                                : "border border-line bg-surface text-ink hover:border-teal/40"
                            }`}
                          >
                            {plan.cta ||
                              (plan.checkoutable === false
                                ? "Contact sales"
                                : "Start Free Trial")}
                          </Link>
                        </div>
                      </article>
                    </Reveal>
                  );
                })}
              </ul>
            )}

            <p className="mt-6 m-0 text-sm text-muted">{pricingCopy.annualNote}</p>
          </div>
        </section>

        {catalog ? (
          <>
            <section
              className="section-pad border-t border-line bg-bg"
              aria-labelledby="trial-heading"
            >
              <div className="content-width grid gap-10 lg:grid-cols-2">
                <div>
                  <SectionHeader
                    eyebrow="Trial"
                    title={pricingCopy.trialTitle}
                    supporting={catalog.trial.summary}
                    id="trial-heading"
                  />
                  <ul className="mt-6 m-0 list-disc space-y-2 pl-5 text-sm text-muted">
                    <li>{catalog.trial.days} days</li>
                    <li>{catalog.trial.voice_minutes} voice minutes</li>
                    <li>{catalog.trial.concurrent_calls} concurrent call</li>
                    <li>
                      Browser voice testing:{" "}
                      {catalog.trial.browser_voice_testing ? "included" : "no"}
                    </li>
                    <li>
                      Credit card required:{" "}
                      {catalog.trial.credit_card_required ? "yes" : "no"}
                    </li>
                  </ul>
                </div>
                <div>
                  <SectionHeader
                    eyebrow="Phone numbers"
                    title={pricingCopy.numbersTitle}
                    supporting="Connect a number you already own or purchase a US local number through the platform."
                  />
                  <ul className="mt-6 m-0 list-none space-y-4 p-0">
                    <li className="rounded-[var(--radius-lg)] border border-line bg-surface p-5">
                      <h3 className="m-0 text-base font-semibold text-ink">
                        Connect existing
                      </h3>
                      <p className="mt-2 m-0 text-sm text-muted">
                        {catalog.number_pricing.connect_existing.summary}
                      </p>
                    </li>
                    <li className="rounded-[var(--radius-lg)] border border-line bg-surface p-5">
                      <h3 className="m-0 text-base font-semibold text-ink">
                        Platform purchase
                      </h3>
                      <p className="mt-2 m-0 text-sm text-muted">
                        {catalog.number_pricing.platform_purchase.summary}
                      </p>
                      <p className="mt-2 m-0 text-sm font-semibold text-ink">
                        {formatMoney(
                          catalog.number_pricing.platform_purchase
                            .us_local_monthly_cents,
                        )}
                        / month for a US local number
                      </p>
                    </li>
                  </ul>
                  {catalog.trial.phone_number_requirements.length > 0 ? (
                    <div className="mt-6">
                      <p className="m-0 text-sm font-semibold text-ink">
                        Before connecting a number
                      </p>
                      <ul className="mt-2 m-0 list-disc space-y-1 pl-5 text-sm text-muted">
                        {catalog.trial.phone_number_requirements.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            </section>

            <section
              className="section-pad border-t border-line bg-surface"
              aria-labelledby="addons-heading"
            >
              <div className="content-width">
                <SectionHeader
                  eyebrow="Add-ons"
                  title={pricingCopy.addOnsTitle}
                  supporting="Optional capacity and services as your operation grows."
                  id="addons-heading"
                />
                <ul className="mt-8 m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
                  {catalog.add_ons.map((addon) => (
                    <li
                      key={addon.key}
                      className="rounded-[var(--radius-lg)] border border-line bg-bg p-5"
                    >
                      <h3 className="m-0 text-base font-semibold text-ink">
                        {addon.name}
                      </h3>
                      <p className="mt-2 m-0 text-sm text-muted">
                        {addon.summary ||
                          (addon.unit_amount != null
                            ? `${formatMoney(addon.unit_amount, addon.currency)}${
                                addon.interval ? ` / ${addon.interval}` : ""
                              }`
                            : "Quoted separately")}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          </>
        ) : null}

        <Faq
          title="Pricing FAQ"
          supporting="Clear answers about AI receptionist and AI voice agent pricing."
          items={pricingFaqs}
        />

        <RelatedLinks
          links={[
            {
              href: "/ai-receptionist",
              label: "AI Receptionist",
              description: "See the front-desk product story.",
            },
            {
              href: "/ai-voice-agents",
              label: "AI Voice Agents",
              description: "Platform capabilities and workflows.",
            },
            {
              href: "/industries",
              label: "Industries",
              description: "How different businesses configure Call & Flow.",
            },
            {
              href: "/signup",
              label: "Start free trial",
              description: "Create a workspace and choose a plan.",
            },
          ]}
        />

        <CtaBand
          title="Start with the plan that matches your volume"
          body="Trial the product in the browser, then connect a number when you are ready to answer real customer calls."
          secondaryHref="/#demo"
          secondaryLabel="Try voice demo"
        />
      </MarketingShell>
    </>
  );
}
