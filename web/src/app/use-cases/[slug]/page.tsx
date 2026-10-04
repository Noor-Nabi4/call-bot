import { notFound } from "next/navigation";
import {
  AlternatingFeatureSection,
  ContentGrid,
  CtaBand,
  Faq,
  JsonLd,
  MarketingImage,
  MarketingShell,
  PageHero,
  RelatedLinks,
  Reveal,
  SectionFlowVisual,
  SectionHeader,
  UseCaseVisual,
} from "@/components/landing";
import { getUseCaseStory } from "@/lib/marketing/feature-sections";
import { getIndustry } from "@/lib/marketing/industries";
import {
  getUseCase,
  getUseCaseSlugs,
} from "@/lib/marketing/use-cases";
import { mediaAssets } from "@/lib/marketing/visuals";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";
import type { SectionFlowVariant } from "@/components/landing/visuals/section-flow-visual";

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
  return getUseCaseSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps) {
  const { slug } = await params;
  const useCase = getUseCase(slug);
  if (!useCase) return {};
  return buildPageMetadata({
    title: useCase.title,
    description: useCase.description,
    path: `/use-cases/${useCase.slug}`,
    keywords: useCase.keywords,
  });
}

export default async function UseCasePage({ params }: PageProps) {
  const { slug } = await params;
  const useCase = getUseCase(slug);
  if (!useCase) notFound();

  const story = getUseCaseStory(useCase.slug);
  const path = `/use-cases/${useCase.slug}`;
  const relatedIndustries = useCase.relatedIndustries
    .map((industrySlug) => getIndustry(industrySlug))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  const relatedUseCases = useCase.relatedUseCases
    .map((relatedSlug) => getUseCase(relatedSlug))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  return (
    <>
      <JsonLd
        data={buildWebPageJsonLd({
          path,
          name: useCase.title,
          description: useCase.description,
        })}
      />
      <JsonLd
        data={buildBreadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: useCase.name, path },
        ])}
      />
      <JsonLd data={buildFaqJsonLd(useCase.faqs)} />

      <MarketingShell>
        <PageHero
          eyebrow={useCase.eyebrow}
          title={useCase.h1}
          supporting={useCase.supporting}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "Use cases" },
            { label: useCase.name },
          ]}
          secondaryCta={{ href: "/ai-voice-agents", label: "AI Voice Agents" }}
          visual={<UseCaseVisual slug={useCase.slug} />}
        />

        {story ? (
          <section
            className="section-pad border-t border-line bg-surface"
            aria-labelledby="use-case-intro-heading"
          >
            <div className="content-width max-w-3xl">
              <Reveal>
                <p className="m-0 mb-3 inline-flex rounded-[var(--radius-sm)] bg-teal-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-teal-deep uppercase">
                  The challenge
                </p>
                <h2
                  id="use-case-intro-heading"
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
              />
            }
          />
        ))}

        {useCase.slug === "appointment-booking" ? (
          <section
            className="section-pad border-t border-line bg-surface"
            aria-labelledby="booking-media-heading"
          >
            <div className="content-width grid items-center gap-10 lg:grid-cols-2">
              <Reveal>
                <SectionHeader
                  eyebrow="From call to calendar"
                  title="Booking happens while the caller is still on the line"
                  supporting="Offer real availability, confirm details, and write appointments your team can trust."
                  id="booking-media-heading"
                />
              </Reveal>
              <Reveal variant="right">
                <div className="overflow-hidden rounded-[var(--radius-xl)] border border-line shadow-[var(--shadow-md)]">
                  <MarketingImage
                    src={mediaAssets.bookingDesk.src}
                    alt={mediaAssets.bookingDesk.alt}
                    width={mediaAssets.bookingDesk.width}
                    height={mediaAssets.bookingDesk.height}
                    className="h-auto w-full object-cover"
                    sizes="(max-width: 1024px) 100vw, 560px"
                  />
                </div>
              </Reveal>
            </div>
          </section>
        ) : null}

        <section
          className="section-pad relative overflow-hidden border-t border-line bg-[#0B1220] text-white"
          aria-labelledby="how-use-case-heading"
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
                  `How ${useCase.name.toLowerCase()} works in Call & Flow`
                }
                supporting={
                  story?.howSupporting ||
                  "Configure the workflow around how your callers already talk."
                }
                id="how-use-case-heading"
                tone="dark"
              />
            </Reveal>
            <ul className="mt-10 m-0 grid list-none gap-4 p-0 sm:grid-cols-2">
              {useCase.capabilities.map((item, index) => (
                <Reveal
                  key={item.title}
                  as="li"
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                >
                  <article className="card-surface-hover h-full rounded-[var(--radius-lg)] border border-white/10 bg-white/[0.04] p-5 shadow-[0_18px_40px_-28px_rgba(0,0,0,0.55)] sm:p-6">
                    <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-white">
                      {item.title}
                    </h3>
                    <p className="mt-2 m-0 text-sm leading-relaxed text-hero-muted">
                      {item.body}
                    </p>
                  </article>
                </Reveal>
              ))}
            </ul>
          </div>
        </section>

        <ContentGrid
          id="outcomes"
          eyebrow="Outcomes"
          title="What teams typically improve"
          supporting="Results depend on call volume, configuration, and how consistently your team uses handoff and booking rules."
          items={useCase.outcomes}
          tone="surface"
        />

        <Faq
          title={`${useCase.name} FAQ`}
          supporting="Search-oriented questions answered without hype."
          items={useCase.faqs}
        />

        <RelatedLinks
          title="Industries that use this workflow"
          links={relatedIndustries.map((industry) => ({
            href: `/industries/${industry.slug}`,
            label: industry.name,
            description: industry.supporting,
          }))}
        />

        <RelatedLinks
          title="Related use cases"
          links={[
            ...relatedUseCases.map((item) => ({
              href: `/use-cases/${item.slug}`,
              label: item.name,
              description: item.supporting,
            })),
            {
              href: "/ai-receptionist",
              label: "AI Receptionist",
              description: "Front-desk answering and after-hours coverage.",
            },
            {
              href: "/pricing",
              label: "Pricing",
              description: "Compare plans and included minutes.",
            },
          ]}
        />

        <CtaBand
          title={`Automate ${useCase.name.toLowerCase()} on your business line`}
          body="Start a free trial and configure the workflow around how your callers already talk."
        />
      </MarketingShell>
    </>
  );
}
