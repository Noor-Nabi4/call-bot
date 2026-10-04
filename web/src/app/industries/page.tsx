import Link from "next/link";
import {
  CtaBand,
  JsonLd,
  MarketingImage,
  MarketingShell,
  PageHero,
  RelatedLinks,
  Reveal,
  SectionHeader,
} from "@/components/landing";
import { industriesHub, industryPages } from "@/lib/marketing/industries";
import { mediaAssets } from "@/lib/marketing/visuals";
import {
  buildBreadcrumbJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";

export const metadata = buildPageMetadata({
  title: industriesHub.title,
  description: industriesHub.description,
  path: "/industries",
  keywords: [
    "AI receptionist by industry",
    "AI voice agents for businesses",
    "industry phone automation",
  ],
});

export default function IndustriesHubPage() {
  return (
    <>
      <JsonLd
        data={buildWebPageJsonLd({
          path: "/industries",
          name: industriesHub.title,
          description: industriesHub.description,
        })}
      />
      <JsonLd
        data={buildBreadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Industries", path: "/industries" },
        ])}
      />

      <MarketingShell>
        <PageHero
          eyebrow="Industries"
          title={industriesHub.h1}
          supporting={industriesHub.supporting}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "Industries" },
          ]}
          secondaryCta={{ href: "/ai-receptionist", label: "AI Receptionist" }}
          visual={
            <div className="overflow-hidden rounded-[var(--radius-xl)] border border-white/10 shadow-[var(--shadow-lg)]">
              <MarketingImage
                src={mediaAssets.industryHub.src}
                alt={mediaAssets.industryHub.alt}
                width={mediaAssets.industryHub.width}
                height={mediaAssets.industryHub.height}
                className="aspect-[4/3] h-auto w-full object-cover"
                sizes="(max-width: 1024px) 100vw, 480px"
                priority
              />
            </div>
          }
        />

        <section
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="industries-list-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Browse"
                title="Choose your industry"
                supporting="Each page covers the call problems, workflows, and FAQs specific to that market — not a find-and-replace template."
                id="industries-list-heading"
              />
            </Reveal>
            <ul className="mt-10 m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {industryPages.map((industry, index) => (
                <Reveal
                  key={industry.slug}
                  as="li"
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                  variant="scale"
                >
                  <Link
                    href={`/industries/${industry.slug}`}
                    className="card-surface card-surface-hover block h-full p-6 no-underline"
                  >
                    <h2 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                      {industry.name}
                    </h2>
                    <p className="mt-3 m-0 text-sm leading-relaxed text-muted">
                      {industry.supporting}
                    </p>
                    <span className="mt-4 inline-block text-sm font-semibold text-teal">
                      View {industry.shortName} →
                    </span>
                  </Link>
                </Reveal>
              ))}
            </ul>
          </div>
        </section>

        <RelatedLinks
          title="Popular product pages"
          links={[
            {
              href: "/ai-receptionist",
              label: "AI Receptionist",
              description: "Virtual front desk for small businesses.",
            },
            {
              href: "/ai-voice-agents",
              label: "AI Voice Agents",
              description: "Platform capabilities across roles.",
            },
            {
              href: "/pricing",
              label: "Pricing",
              description: "Compare plans and included minutes.",
            },
          ]}
        />

        <CtaBand />
      </MarketingShell>
    </>
  );
}
