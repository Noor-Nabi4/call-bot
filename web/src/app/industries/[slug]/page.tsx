import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ContentGrid,
  CtaBand,
  Faq,
  JsonLd,
  MarketingShell,
  PageHero,
  RelatedLinks,
  Reveal,
  SectionHeader,
} from "@/components/landing";
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
        />

        <ContentGrid
          id="problems"
          eyebrow="The phone problem"
          title={`Why ${industry.shortName} miss calls`}
          items={industry.problems}
          columns={3}
          tone="surface"
        />

        <ContentGrid
          id="scenarios"
          eyebrow="Call scenarios"
          title="Real conversations your line already gets"
          items={industry.scenarios}
          columns={3}
        />

        <section
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="workflows-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Workflows"
                title={`How Call & Flow helps ${industry.shortName}`}
                supporting="Configure the workflows that match your dispatch, intake, or front-desk process."
                id="workflows-heading"
              />
            </Reveal>
            <ol className="mt-10 m-0 grid list-none gap-4 p-0 sm:grid-cols-2">
              {industry.workflows.map((workflow, index) => (
                <Reveal
                  key={workflow.title}
                  as="li"
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                >
                  <article className="flex h-full gap-4 rounded-[var(--radius-lg)] border border-line bg-bg p-5">
                    <span className="font-mono text-sm text-teal">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                        {workflow.title}
                      </h3>
                      <p className="mt-2 m-0 text-sm leading-relaxed text-muted">
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
