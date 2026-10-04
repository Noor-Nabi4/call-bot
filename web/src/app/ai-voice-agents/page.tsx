import {
  ContentGrid,
  CtaBand,
  Faq,
  HowItWorksSection,
  JsonLd,
  MarketingShell,
  PageHero,
  RelatedLinks,
} from "@/components/landing";
import { howItWorks } from "@/lib/copy";
import { aiVoiceAgentsPage } from "@/lib/marketing/product-pages";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";

const page = aiVoiceAgentsPage;

export const metadata = buildPageMetadata({
  title: page.title,
  description: page.description,
  path: page.path,
  keywords: page.keywords,
});

export default function AiVoiceAgentsPage() {
  return (
    <>
      <JsonLd
        data={buildWebPageJsonLd({
          path: page.path,
          name: page.title,
          description: page.description,
        })}
      />
      <JsonLd
        data={buildBreadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "AI Voice Agents", path: page.path },
        ])}
      />
      <JsonLd data={buildFaqJsonLd(page.faqs)} />

      <MarketingShell>
        <PageHero
          eyebrow={page.eyebrow}
          title={page.h1}
          supporting={page.supporting}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "AI Voice Agents" },
          ]}
          secondaryCta={{ href: "/ai-receptionist", label: "AI Receptionist" }}
        />

        <ContentGrid
          id="capabilities"
          eyebrow="What AI voice agents handle"
          title="Phone work across the full conversation"
          supporting="Use one platform for the inbound workflows US businesses actually run — without unsupported claims or fake automation promises."
          items={page.pillars}
          columns={2}
          tone="surface"
        />

        <ContentGrid
          id="platform"
          eyebrow="Platform"
          title="An AI voice agent platform operators can run"
          items={page.platformPoints}
        />

        <HowItWorksSection
          title={howItWorks.title}
          supporting={howItWorks.supporting}
          steps={howItWorks.steps}
        />

        <Faq
          title="AI voice agent FAQ"
          supporting="Practical answers for teams evaluating AI voice automation."
          items={page.faqs}
        />

        <RelatedLinks
          links={[
            {
              href: "/ai-receptionist",
              label: "AI Receptionist",
              description: "Front-desk answering, booking, and after-hours coverage.",
            },
            {
              href: "/industries",
              label: "Industries",
              description: "See how different businesses configure voice agents.",
            },
            {
              href: "/use-cases/lead-qualification",
              label: "Lead qualification",
              description: "Capture and qualify inbound opportunities.",
            },
            {
              href: "/pricing",
              label: "AI voice agent pricing",
              description: "Plans based on minutes and concurrency.",
            },
          ]}
        />

        <CtaBand
          title="Deploy AI voice agents on your business lines"
          body="Start a free trial, pick a template, and automate the phone work your team should not have to repeat."
        />
      </MarketingShell>
    </>
  );
}
