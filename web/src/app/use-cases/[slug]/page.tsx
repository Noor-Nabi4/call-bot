import { notFound } from "next/navigation";
import {
  ContentGrid,
  CtaBand,
  Faq,
  JsonLd,
  MarketingShell,
  PageHero,
  RelatedLinks,
} from "@/components/landing";
import { getIndustry } from "@/lib/marketing/industries";
import {
  getUseCase,
  getUseCaseSlugs,
} from "@/lib/marketing/use-cases";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";

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
        />

        <ContentGrid
          id="problems"
          eyebrow="The challenge"
          title="Why this workflow breaks on busy phone lines"
          items={useCase.problems}
          tone="surface"
        />

        <ContentGrid
          id="capabilities"
          eyebrow="What Call & Flow does"
          title={`Capabilities for ${useCase.name.toLowerCase()}`}
          items={useCase.capabilities}
          columns={2}
        />

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
