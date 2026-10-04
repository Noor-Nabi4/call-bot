import Link from "next/link";
import {
  Button,
  Faq,
  FeatureShowcase,
  Footer,
  Hero,
  HowItWorksSection,
  MarketingImage,
  Navbar,
  PricingSection,
  Reveal,
  SectionHeader,
  VoiceDemoSection,
} from "@/components/landing";
import { mediaAssets } from "@/lib/marketing/visuals";
import { site } from "@/lib/copy";
import {
  close,
  faq,
  features,
  howItWorks,
  industries,
  pricingPreview,
} from "@/lib/copy";
import {
  fetchPricingCatalog,
  formatPlanPrice,
  type Plan,
} from "@/lib/marketing-api";
import {
  buildFaqJsonLd,
  buildHomePageJsonLd,
  buildPageMetadata,
} from "@/lib/metadata";
import { faqItems, seo } from "@/lib/seo";

export const metadata = buildPageMetadata({
  title: seo.title,
  description: seo.description,
  path: "/",
  absoluteTitle: true,
  keywords: seo.keywords,
});

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
  const homeJsonLd = buildHomePageJsonLd();
  const plans = await loadPlans();

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(homeJsonLd) }}
      />
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
          className="section-pad border-t border-line bg-bg"
          aria-labelledby="product-links-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Explore the product"
                title="AI voice agents built for real phone work"
                supporting="Start with the page that matches how you search — then see pricing and industry workflows."
                id="product-links-heading"
                align="center"
              />
              <p className="mx-auto mt-4 m-0 max-w-2xl text-center text-base leading-relaxed text-muted">
                From booking and lead qualification to customer support and call
                answering,{" "}
                <Link
                  href="/use-cases"
                  className="font-medium text-teal underline-offset-4 hover:underline"
                >
                  explore AI voice-agent use cases
                </Link>{" "}
                businesses use to automate phone work.
              </p>
            </Reveal>
            <ul className="mt-10 m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  href: "/ai-voice-agents",
                  title: "AI Voice Agents",
                  body: "Platform overview for inbound automation, booking, support, and handoff.",
                },
                {
                  href: "/ai-receptionist",
                  title: "AI Receptionist",
                  body: "Virtual front desk that answers, books, qualifies, and transfers.",
                },
                {
                  href: "/industries",
                  title: "Industries",
                  body: "HVAC, plumbing, healthcare, legal, real estate, restaurants, and more.",
                },
                {
                  href: "/pricing",
                  title: "Pricing",
                  body: "Plans based on minutes, concurrency, numbers, users, and knowledge.",
                },
              ].map((item, index) => (
                <Reveal
                  key={item.href}
                  as="li"
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                  variant="scale"
                >
                  <Link
                    href={item.href}
                    className="card-surface card-surface-hover block h-full p-5 no-underline sm:p-6"
                  >
                    <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                      {item.title}
                    </h3>
                    <p className="mt-2 m-0 text-sm leading-relaxed text-muted">
                      {item.body}
                    </p>
                    <span className="mt-4 inline-block text-sm font-semibold text-teal">
                      Learn more →
                    </span>
                  </Link>
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
          className="section-pad border-t border-line bg-bg"
          aria-labelledby="ops-visual-heading"
        >
          <div className="content-width grid items-center gap-10 lg:grid-cols-2">
            <Reveal>
              <SectionHeader
                eyebrow="Built for operators"
                title="See calls, bookings, and handoffs in one place"
                supporting="Call & Flow is not just a demo voice. It is a multi-tenant ops platform for the teams that own the phones."
                id="ops-visual-heading"
              />
              <div className="mt-6">
                <Button href="/ai-voice-agents" variant="secondary">
                  Explore AI voice agents
                </Button>
              </div>
            </Reveal>
            <Reveal variant="right">
              <div className="overflow-hidden rounded-[var(--radius-xl)] border border-line shadow-[var(--shadow-md)]">
                <MarketingImage
                  src={mediaAssets.voiceOps.src}
                  alt={mediaAssets.voiceOps.alt}
                  width={mediaAssets.voiceOps.width}
                  height={mediaAssets.voiceOps.height}
                  className="h-auto w-full object-cover"
                  sizes="(max-width: 1024px) 100vw, 560px"
                />
              </div>
            </Reveal>
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
                  <Link
                    href={item.href}
                    className="card-surface card-surface-hover block h-full p-5 no-underline sm:p-6"
                  >
                    <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                      {item.name}
                    </h3>
                    <p className="mt-2 m-0 text-sm leading-relaxed text-muted sm:text-base">
                      {item.body}
                    </p>
                  </Link>
                </Reveal>
              ))}
            </ul>
            <div className="mt-8 text-center">
              <Link
                href="/industries"
                className="text-sm font-semibold text-teal transition-colors hover:text-teal-deep"
              >
                Browse all industries →
              </Link>
            </div>
          </div>
        </section>

        <PricingSection
          title={pricingPreview.title}
          supporting={pricingPreview.supporting}
          compareHref="/pricing"
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
