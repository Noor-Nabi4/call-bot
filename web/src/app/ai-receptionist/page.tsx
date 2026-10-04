import Link from "next/link";
import {
  ContentGrid,
  CtaBand,
  Faq,
  HowItWorksSection,
  JsonLd,
  MarketingShell,
  PageHero,
  RelatedLinks,
  Reveal,
  SectionHeader,
} from "@/components/landing";
import { howItWorks } from "@/lib/copy";
import { industryPages } from "@/lib/marketing/industries";
import { aiReceptionistPage } from "@/lib/marketing/product-pages";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";

const page = aiReceptionistPage;

export const metadata = buildPageMetadata({
  title: page.title,
  description: page.description,
  path: page.path,
  keywords: page.keywords,
});

export default function AiReceptionistPage() {
  const crumbs = [
    { name: "Home", path: "/" },
    { name: "AI Receptionist", path: page.path },
  ];

  return (
    <>
      <JsonLd data={buildWebPageJsonLd({
        path: page.path,
        name: page.title,
        description: page.description,
      })} />
      <JsonLd data={buildBreadcrumbJsonLd(crumbs)} />
      <JsonLd data={buildFaqJsonLd(page.faqs)} />

      <MarketingShell>
        <PageHero
          eyebrow={page.eyebrow}
          title={page.h1}
          supporting={page.supporting}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "AI Receptionist" },
          ]}
          secondaryCta={{ href: "/pricing", label: "See pricing" }}
        />

        <ContentGrid
          id="what-it-does"
          eyebrow="Overview"
          title={page.whatItDoes.title}
          supporting={page.whatItDoes.supporting}
          items={page.whatItDoes.items}
          tone="surface"
        />

        <section
          className="section-pad border-t border-line bg-bg"
          aria-labelledby="receptionist-capabilities-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Capabilities"
                title="Built for the calls your front desk already takes"
                supporting="Each workflow is available inside one AI receptionist agent — configure the ones your business needs."
                id="receptionist-capabilities-heading"
              />
            </Reveal>
            <div className="mt-10 grid gap-6 lg:grid-cols-2">
              {page.sections.map((section, index) => (
                <Reveal
                  key={section.id}
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                  as="article"
                  className="card-surface h-full scroll-mt-28 p-6 sm:p-7"
                >
                  <div id={section.id}>
                    <h2 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                      {section.title}
                    </h2>
                    <p className="mt-3 m-0 text-base leading-relaxed text-muted">
                      {section.body}
                    </p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="receptionist-industries-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Industries"
                title="AI receptionist use cases by industry"
                supporting={page.industriesIntro}
                id="receptionist-industries-heading"
              />
            </Reveal>
            <ul className="mt-8 m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {industryPages.slice(0, 6).map((industry) => (
                <li key={industry.slug}>
                  <Link
                    href={`/industries/${industry.slug}`}
                    className="card-surface card-surface-hover block h-full p-5 no-underline"
                  >
                    <span className="text-base font-semibold text-ink">
                      {industry.name}
                    </span>
                    <span className="mt-2 block text-sm text-muted">
                      {industry.supporting.slice(0, 120)}…
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <div className="mt-6">
              <Link
                href="/industries"
                className="text-sm font-semibold text-teal hover:text-teal-deep"
              >
                View all industries →
              </Link>
            </div>
          </div>
        </section>

        <HowItWorksSection
          title={page.howItWorksTitle}
          supporting={page.howItWorksSupporting}
          steps={howItWorks.steps}
        />

        <ContentGrid
          id="features"
          eyebrow="Features"
          title="What you get with Call & Flow"
          items={page.features}
          tone="surface"
        />

        <Faq
          title="AI receptionist FAQ"
          supporting="Common questions from US businesses evaluating an AI receptionist service."
          items={page.faqs}
        />

        <RelatedLinks
          title="Keep exploring"
          links={[
            {
              href: "/ai-voice-agents",
              label: "AI Voice Agents",
              description: "See the full platform for phone automation.",
            },
            {
              href: "/use-cases/call-answering",
              label: "AI call answering",
              description: "Always-on coverage for busy business lines.",
            },
            {
              href: "/use-cases/appointment-booking",
              label: "Appointment booking",
              description: "Book visits while the caller is still on the line.",
            },
            {
              href: "/pricing",
              label: "Pricing",
              description: "Minutes, concurrency, numbers, and overage rates.",
            },
          ]}
        />

        <CtaBand
          title="Put an AI receptionist on your business line"
          body="Start a free trial, configure your greeting and booking rules, and answer calls even when your team is busy."
        />
      </MarketingShell>
    </>
  );
}
