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
import { useCasePages, useCasesHub } from "@/lib/marketing/use-cases";
import { mediaAssets } from "@/lib/marketing/visuals";
import {
  buildBreadcrumbJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";

export const metadata = buildPageMetadata({
  title: useCasesHub.title,
  description: useCasesHub.description,
  path: "/use-cases",
  keywords: [
    "AI voice agent use cases",
    "AI appointment booking",
    "AI call answering",
    "AI lead qualification",
  ],
});

export default function UseCasesHubPage() {
  return (
    <>
      <JsonLd
        data={buildWebPageJsonLd({
          path: "/use-cases",
          name: useCasesHub.title,
          description: useCasesHub.description,
        })}
      />
      <JsonLd
        data={buildBreadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Use Cases", path: "/use-cases" },
        ])}
      />

      <MarketingShell>
        <PageHero
          eyebrow="Use cases"
          title={useCasesHub.h1}
          supporting={useCasesHub.supporting}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "Use cases" },
          ]}
          secondaryCta={{ href: "/ai-voice-agents", label: "AI Voice Agents" }}
          visual={
            <div className="overflow-hidden rounded-[var(--radius-xl)] border border-white/10 shadow-[var(--shadow-lg)]">
              <MarketingImage
                src={mediaAssets.bookingDesk.src}
                alt={mediaAssets.bookingDesk.alt}
                width={mediaAssets.bookingDesk.width}
                height={mediaAssets.bookingDesk.height}
                className="aspect-[4/3] h-auto w-full object-cover"
                sizes="(max-width: 1024px) 100vw, 480px"
                priority
              />
            </div>
          }
        />

        <section
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="use-cases-list-heading"
        >
          <div className="content-width">
            <Reveal>
              <SectionHeader
                eyebrow="Browse"
                title="Choose a call workflow"
                supporting="Each page focuses on one commercial outcome — not a generic AI brochure. Pair a use case with your industry page when you are ready to launch."
                id="use-cases-list-heading"
              />
            </Reveal>
            <ul className="mt-10 m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {useCasePages.map((useCase, index) => (
                <Reveal
                  key={useCase.slug}
                  as="li"
                  delay={(index % 3) as 0 | 1 | 2 | 3}
                  variant="scale"
                >
                  <Link
                    href={`/use-cases/${useCase.slug}`}
                    className="card-surface card-surface-hover block h-full p-6 no-underline"
                  >
                    <h2 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                      {useCase.name}
                    </h2>
                    <p className="mt-3 m-0 text-sm leading-relaxed text-muted">
                      {useCase.supporting}
                    </p>
                    <span className="mt-4 inline-block text-sm font-semibold text-teal">
                      View {useCase.name.toLowerCase()} →
                    </span>
                  </Link>
                </Reveal>
              ))}
            </ul>
            <p className="mt-8 m-0 max-w-3xl text-sm leading-relaxed text-muted">
              Looking for the product category instead of a workflow? Start with{" "}
              <Link
                href="/ai-receptionist"
                className="font-semibold text-teal hover:text-teal-deep"
              >
                AI Receptionist
              </Link>{" "}
              for front-desk answering, or{" "}
              <Link
                href="/ai-voice-agents"
                className="font-semibold text-teal hover:text-teal-deep"
              >
                AI Voice Agents
              </Link>{" "}
              for the broader phone automation platform.
            </p>
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
              href: "/industries",
              label: "Industries",
              description: "See how workflows adapt by market.",
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
