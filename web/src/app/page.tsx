import {
  BenefitCard,
  Button,
  Faq,
  FeatureCard,
  FeatureShowcase,
  Footer,
  Hero,
  HowItWorksSection,
  LogoCloud,
  Navbar,
  PricingSection,
  Reveal,
  SectionHeader,
  TestimonialCard,
} from "@/components/landing";
import { site } from "@/lib/copy";
import {
  IconBook,
  IconCalendar,
  IconChart,
  IconHandoff,
  IconLayers,
  IconWave,
} from "@/components/landing/icons";
import {
  analytics,
  close,
  faq,
  features,
  howItWorks,
  industries,
  integrations,
  platform,
  pricingPreview,
  testimonials,
  trustedBy,
  whyChoose,
} from "@/lib/copy";
import {
  fetchPricingCatalog,
  formatPlanPrice,
  type Plan,
} from "@/lib/api";
import { buildFaqJsonLd } from "@/lib/metadata";
import { faqItems } from "@/lib/seo";
import { playgroundUrl } from "@/lib/site-urls";

const featureIcons = [
  <IconWave key="wave" />,
  <IconCalendar key="cal" />,
  <IconBook key="book" />,
  <IconHandoff key="hand" />,
  <IconLayers key="layers" />,
  <IconChart key="chart" />,
];

async function loadPlans(): Promise<Plan[]> {
  try {
    const catalog = await fetchPricingCatalog(true);
    const plans = catalog.plans.slice(0, 3);
    if (catalog.enterprise && plans.length < 3) {
      return [...plans, catalog.enterprise].slice(0, 3);
    }
    return plans;
  } catch {
    return [];
  }
}

export default async function LandingPage() {
  const faqJsonLd = buildFaqJsonLd(faqItems);
  const plans = await loadPlans();

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />

      <main id="main-content">
        <Navbar brand={site.brand} />
        <Hero />

        <LogoCloud title={trustedBy.title} logos={trustedBy.logos} />

        <section
          className="section-pad bg-bg"
          aria-labelledby="why-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Why CallBot"
                title={whyChoose.title}
                supporting={whyChoose.supporting}
                id="why-heading"
              />
            </Reveal>
            <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {whyChoose.items.map((item, index) => (
                <Reveal key={item.title} delay={(index % 3) as 0 | 1 | 2 | 3}>
                  <BenefitCard
                    index={index + 1}
                    title={item.title}
                    body={item.body}
                  />
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <FeatureShowcase
          title={platform.title}
          supporting={platform.supporting}
          items={platform.items}
        />

        <section
          id="features"
          className="section-pad border-t border-line bg-bg"
          aria-labelledby="features-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Capabilities"
                title={features.title}
                supporting={features.supporting}
                id="features-heading"
                align="center"
              />
            </Reveal>
            <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {features.items.map((item, index) => (
                <Reveal key={item.title} delay={(index % 3) as 0 | 1 | 2 | 3}>
                  <FeatureCard
                    title={item.title}
                    body={item.body}
                    icon={featureIcons[index]}
                  />
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section
          id="industries"
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="industries-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Industries"
                title={industries.title}
                supporting={industries.supporting}
                id="industries-heading"
              />
            </Reveal>
            <ul className="mt-12 m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {industries.items.map((item, index) => (
                <Reveal
                  key={item.name}
                  as="li"
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                >
                  <article className="card-surface card-surface-hover h-full p-6">
                    <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                      {item.name}
                    </h3>
                    <p className="mt-2 m-0 text-base leading-relaxed text-muted">
                      {item.body}
                    </p>
                  </article>
                </Reveal>
              ))}
            </ul>
          </div>
        </section>

        <HowItWorksSection
          title={howItWorks.title}
          supporting={howItWorks.supporting}
          steps={howItWorks.steps}
        />

        <section
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="integrations-heading"
        >
          <div className="content-width grid gap-12 lg:grid-cols-2 lg:items-center">
            <Reveal>
              <SectionHeader
                eyebrow="Integrations"
                title={integrations.title}
                supporting={integrations.supporting}
                id="integrations-heading"
              />
            </Reveal>
            <div className="grid gap-4 sm:grid-cols-2">
              {integrations.items.map((item, index) => (
                <Reveal key={item.title} delay={(index % 3) as 0 | 1 | 2 | 3}>
                  <article className="rounded-[var(--radius-lg)] border border-line bg-bg p-5">
                    <h3 className="m-0 text-base font-semibold tracking-[-0.02em] text-ink">
                      {item.title}
                    </h3>
                    <p className="mt-2 m-0 text-sm leading-relaxed text-muted">
                      {item.body}
                    </p>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section
          className="section-pad relative overflow-hidden border-t border-line bg-ink text-white"
          aria-labelledby="analytics-heading"
        >
          <div
            className="pointer-events-none absolute inset-0 opacity-80"
            aria-hidden="true"
            style={{
              background:
                "radial-gradient(60% 50% at 80% 20%, rgba(14,143,125,0.25), transparent 60%), radial-gradient(50% 40% at 10% 80%, rgba(47,111,173,0.2), transparent 55%)",
            }}
          />
          <div className="relative z-[1] content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Analytics"
                title={analytics.title}
                supporting={analytics.supporting}
                id="analytics-heading"
                tone="dark"
              />
            </Reveal>
            <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {analytics.metrics.map((metric, index) => (
                <Reveal key={metric.label} delay={(index % 3) as 0 | 1 | 2 | 3}>
                  <article className="rounded-[var(--radius-lg)] border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
                    <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-white">
                      {metric.label}
                    </h3>
                    <p className="mt-2 m-0 text-sm leading-relaxed text-hero-muted">
                      {metric.body}
                    </p>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <PricingSection
          title={pricingPreview.title}
          supporting={pricingPreview.supporting}
          compareHref="/signup"
          compareLabel={pricingPreview.cta}
          emptyNote={pricingPreview.note}
          plans={plans.map((plan) => ({
            key: plan.key,
            name: plan.name,
            tagline: plan.tagline,
            price: formatPlanPrice(plan),
            features: plan.highlights ?? plan.features,
            href: plan.checkoutable === false
              ? "/signup"
              : `/signup?plan=${encodeURIComponent(plan.key)}`,
            cta: plan.cta || (plan.checkoutable === false ? "Contact sales" : "Start Free Trial"),
            popular: plan.popular,
          }))}
        />

        <section
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="testimonials-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Customer stories"
                title={testimonials.title}
                supporting={testimonials.supporting}
                id="testimonials-heading"
                align="center"
              />
            </Reveal>
            <div className="mt-12 grid gap-5 lg:grid-cols-3">
              {testimonials.items.map((item, index) => (
                <Reveal key={item.role} delay={(index % 3) as 0 | 1 | 2 | 3}>
                  <TestimonialCard
                    quote={item.quote}
                    name={item.name}
                    role={item.role}
                  />
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <Faq title={faq.title} supporting={faq.supporting} items={faqItems} />

        <section
          className="relative overflow-hidden bg-hero px-6 py-24 text-white sm:px-10 lg:px-12"
          aria-labelledby="close-heading"
        >
          <div
            className="pointer-events-none absolute inset-0"
            aria-hidden="true"
            style={{
              background:
                "radial-gradient(70% 60% at 50% 0%, rgba(20,184,160,0.28), transparent 60%)",
            }}
          />
          <Reveal variant="scale" className="relative z-[1] mx-auto flex max-w-3xl flex-col items-start gap-6 sm:items-center sm:text-center">
            <h2
              id="close-heading"
              className="font-display m-0 text-[clamp(2rem,4.5vw,3.25rem)] font-semibold leading-[1.05] tracking-[-0.04em]"
            >
              {close.title}
            </h2>
            <p className="m-0 max-w-xl text-base leading-relaxed text-hero-muted sm:text-lg">
              {close.body}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-3 sm:justify-center">
              <Button href="/signup" variant="inverse" size="lg">
                {close.primaryCta}
              </Button>
              <Button href="/#pricing" variant="outline-light" size="lg">
                {close.secondaryCta}
              </Button>
              <Button
                href={playgroundUrl()}
                variant="outline-light"
                size="lg"
                className="sm:hidden"
              >
                Book Demo
              </Button>
            </div>
          </Reveal>
        </section>

        <Footer />
      </main>
    </>
  );
}
