import Link from "next/link";
import { notFound } from "next/navigation";
import {
  AlternatingFeatureSection,
  ContentGrid,
  CtaBand,
  Faq,
  IndustryVisual,
  JsonLd,
  MarketingShell,
  PageHero,
  RelatedLinks,
  Reveal,
  SectionFlowVisual,
  SectionHeader,
} from "@/components/landing";
import { getIndustryStory } from "@/lib/marketing/feature-sections";
import {
  getIndustry,
  getIndustrySlugs,
  industryPages,
} from "@/lib/marketing/industries";
import { getUseCase } from "@/lib/marketing/use-cases";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";
import type { SectionFlowVariant } from "@/components/landing/visuals/section-flow-visual";
import { getIndustryStoryMedia } from "@/lib/marketing/human-assets";
import { getIndustryBusinessVisual } from "@/lib/marketing/human-business-visuals";

const STORY_VISUAL_VARIANTS: readonly SectionFlowVariant[] = [
  "spotlight",
  "flow",
  "stack",
  "handoff",
];

type PageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return getIndustrySlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps) {
  const { slug } = await params;
  const industry = getIndustry(slug);
  if (!industry) return {};
  return buildPageMetadata({
    title: industry.title,
    description: industry.description,
    path: `/industries/${industry.slug}`,
    keywords: industry.keywords,
  });
}

export default async function IndustryPage({ params }: PageProps) {
  const { slug } = await params;
  const industry = getIndustry(slug);
  if (!industry) notFound();

  const story = getIndustryStory(industry.slug);
  const storyMedia = getIndustryStoryMedia(industry.slug);
  const businessVisual = getIndustryBusinessVisual(industry.slug);
  const path = `/industries/${industry.slug}`;
  const related = industry.relatedSlugs
    .map((relatedSlug) => getIndustry(relatedSlug))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  const useCaseLinks = industry.useCaseHrefs.map((href) => {
    const useCaseSlug = href.replace("/use-cases/", "");
    const useCase = getUseCase(useCaseSlug);
    return {
      href,
      label: useCase?.name || useCaseSlug,
      description: useCase?.supporting,
    };
  });

  return (
    <>
      <JsonLd
        data={buildWebPageJsonLd({
          path,
          name: industry.title,
          description: industry.description,
        })}
      />
      <JsonLd
        data={buildBreadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Industries", path: "/industries" },
          { name: industry.name, path },
        ])}
      />
      <JsonLd data={buildFaqJsonLd(industry.faqs)} />

      <MarketingShell>
        <PageHero
          eyebrow={industry.eyebrow}
          title={industry.h1}
          supporting={industry.supporting}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "Industries", href: "/industries" },
            { label: industry.name },
          ]}
          secondaryCta={{ href: "/pricing", label: "See pricing" }}
          visual={
            <IndustryVisual slug={industry.slug} industryName={industry.name} />
          }
        />

        {story ? (
          <section
            className="section-pad border-t border-line bg-surface"
            aria-labelledby="industry-intro-heading"
          >
            <div className="content-width max-w-3xl">
              <Reveal>
                <p className="m-0 mb-3 inline-flex rounded-[var(--radius-sm)] bg-teal-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-teal-deep uppercase">
                  The phone problem
                </p>
                <h2
                  id="industry-intro-heading"
                  className="font-display m-0 text-[clamp(1.75rem,3.4vw,2.55rem)] font-semibold leading-[1.1] tracking-[-0.04em] text-ink"
                >
                  {story.introTitle}
                </h2>
                <p className="mt-4 m-0 text-base leading-relaxed text-muted sm:text-lg">
                  {story.introBody}
                </p>
              </Reveal>
            </div>
          </section>
        ) : null}

        {story?.sections.map((section, index) => (
          <AlternatingFeatureSection
            key={section.id}
            id={section.id}
            eyebrow={section.eyebrow}
            title={section.title}
            description={section.description}
            bullets={section.bullets}
            badge={section.badge}
            cta={section.cta}
            tone={
              index === 3
                ? "elevated"
                : index % 2 === 0
                  ? "bg"
                  : "surface"
            }
            reverse={index % 2 === 1}
            visual={
              <SectionFlowVisual
                title={section.flow.title}
                alt={section.flow.alt}
                steps={section.flow.steps}
                tone={index % 2 === 1 ? "light" : "dark"}
                variant={STORY_VISUAL_VARIANTS[index % 4]}
                media={storyMedia[index % 4]}
                businessVisual={
                  index % 4 === 0 ? businessVisual : null
                }
              />
            }
          />
        ))}

        <section
          className="section-pad relative overflow-hidden border-t border-line bg-[#0B1220] text-white"
          aria-labelledby="how-industry-heading"
        >
          <div
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(80%_60%_at_10%_0%,rgba(20,184,160,0.18),transparent_55%),radial-gradient(70%_50%_at_100%_100%,rgba(14,165,233,0.12),transparent_50%)]"
            aria-hidden="true"
          />
          <div className="relative z-[1] content-width">
            <Reveal>
              <SectionHeader
                eyebrow="How it works"
                title={
                  story?.howTitle ||
                  `How Call & Flow helps ${industry.shortName}`
                }
                supporting={
                  story?.howSupporting ||
                  "Configure the workflows that match your dispatch, intake, or front-desk process."
                }
                id="how-industry-heading"
                tone="dark"
              />
            </Reveal>
            <ol className="mt-10 m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {industry.workflows.slice(0, 6).map((workflow, index) => (
                <Reveal
                  key={workflow.title}
                  as="li"
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                >
                  <article className="card-surface-hover flex h-full gap-4 rounded-[var(--radius-lg)] border border-white/10 bg-white/[0.04] p-5 shadow-[0_18px_40px_-28px_rgba(0,0,0,0.55)]">
                    <span className="font-mono text-sm text-teal-bright">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-white">
                        {workflow.title}
                      </h3>
                      <p className="mt-2 m-0 text-sm leading-relaxed text-hero-muted">
                        {workflow.body}
                      </p>
                    </div>
                  </article>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        <ContentGrid
          id="scenarios"
          eyebrow="Call scenarios"
          title="Real conversations your line already gets"
          items={industry.scenarios}
          columns={3}
          tone="surface"
        />

        <ContentGrid
          id="benefits"
          eyebrow="Benefits"
          title="What changes when every call is answered"
          items={industry.benefits}
          columns={3}
        />

        <Faq
          title={`${industry.name} FAQ`}
          supporting={`Questions ${industry.shortName} ask before launching an AI receptionist.`}
          items={industry.faqs}
        />

        <RelatedLinks
          title="Related industries"
          supporting="Explore nearby verticals with similar phone workflows."
          links={related.map((item) => ({
            href: `/industries/${item.slug}`,
            label: item.name,
            description: item.supporting,
          }))}
        />

        <RelatedLinks
          title="Related use cases"
          links={[
            ...useCaseLinks,
            {
              href: "/ai-receptionist",
              label: "AI Receptionist",
              description: "Front-desk answering for small businesses.",
            },
            {
              href: "/ai-voice-agents",
              label: "AI Voice Agents",
              description: "Platform overview for phone automation.",
            },
            {
              href: "/pricing",
              label: "Pricing",
              description: "Compare plans and included minutes.",
            },
          ]}
        />

        <section className="border-t border-line bg-bg px-6 py-8 text-center sm:px-10">
          <p className="m-0 text-sm text-muted">
            Looking for a different market?{" "}
            <Link href="/industries" className="font-semibold text-teal">
              Browse all {industryPages.length} industries
            </Link>
            .
          </p>
        </section>

        <CtaBand
          title={`Put an AI receptionist on your ${industry.name.toLowerCase()} line`}
          body="Start a free trial, customize the intake questions your callers expect, and stop losing jobs to voicemail."
        />
      </MarketingShell>
    </>
  );
}
