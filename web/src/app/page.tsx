import {
  Button,
  Faq,
  FeatureShowcase,
  Footer,
  Hero,
  Navbar,
  PricingSection,
  Reveal,
  SectionHeader,
  VoiceDemoSection,
} from "@/components/landing";
import { site } from "@/lib/copy";
import {
  close,
  faq,
  features,
  industries,
  pricingPreview,
} from "@/lib/copy";
import {
  fetchPricingCatalog,
  formatPlanPrice,
  type Plan,
} from "@/lib/marketing-api";
import { buildFaqJsonLd } from "@/lib/metadata";
import { faqItems } from "@/lib/seo";

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
        <VoiceDemoSection />

        <FeatureShowcase
          title={features.title}
          supporting={features.supporting}
          items={features.items}
        />

        <section
          id="industries"
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="industries-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Industry templates"
                title={industries.title}
                supporting={industries.supporting}
                id="industries-heading"
                align="center"
              />
            </Reveal>
            <ul className="mt-10 m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {industries.items.map((item, index) => (
                <Reveal
                  key={item.name}
                  as="li"
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                  variant="scale"
                >
                  <article className="card-surface card-surface-hover h-full p-5 sm:p-6">
                    <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                      {item.name}
                    </h3>
                    <p className="mt-2 m-0 text-sm leading-relaxed text-muted sm:text-base">
                      {item.body}
                    </p>
                  </article>
                </Reveal>
              ))}
            </ul>
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
            href:
              plan.checkoutable === false
                ? "/signup"
                : `/signup?plan=${encodeURIComponent(plan.key)}`,
            cta:
              plan.cta ||
              (plan.checkoutable === false
                ? "Contact sales"
                : "Start Free Trial"),
            popular: plan.popular,
          }))}
        />

        <Faq title={faq.title} supporting={faq.supporting} items={faqItems} />

        <section
          className="relative overflow-hidden bg-hero px-6 py-20 text-white sm:px-10 lg:px-12"
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
          <Reveal
            variant="scale"
            className="relative z-[1] mx-auto flex max-w-3xl flex-col items-start gap-6 sm:items-center sm:text-center"
          >
            <h2
              id="close-heading"
              className="font-display m-0 text-[clamp(2rem,4.5vw,3.1rem)] font-semibold leading-[1.05] tracking-[-0.04em]"
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
              <Button href="#demo" variant="outline-light" size="lg">
                {close.secondaryCta}
              </Button>
            </div>
          </Reveal>
        </section>

        <Footer />
      </main>
    </>
  );
}
