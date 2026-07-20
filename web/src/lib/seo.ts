/** SEO configuration for the Call Bot marketing site. */

export function getSiteUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
    process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim() ||
    process.env.VERCEL_URL?.trim() ||
    "http://localhost:3002";
  const withProtocol = raw.startsWith("http") ? raw : `https://${raw}`;
  return withProtocol.replace(/\/$/, "");
}

export const seo = {
  brand: "Call Bot",
  title: "Call Bot | AI Phone Agents for Growing Businesses",
  titleTemplate: "%s | Call Bot",
  description:
    "Call Bot answers every call in your brand’s voice, books appointments, hands off to humans, and runs multi-tenant ops — with marketplace agents, live monitoring, and a public API.",
  keywords: [
    "AI phone receptionist",
    "AI voice assistant for business",
    "AI answering service",
    "marketplace AI agents",
    "multi-tenant voice agent",
    "AI call center ops",
    "live call monitoring",
    "voice AI scheduling",
    "HVAC call answering AI",
    "medical appointment AI receptionist",
    "restaurant reservation AI",
    "SIP telephony voice AI",
    "LiveKit voice agent",
    "AI receptionist that books appointments",
    "business voice API",
    "Call Bot",
  ],
  locale: "en_US",
  ogImageAlt: "Call Bot — AI phone agents with marketplace installs and ops",
  twitterHandle: "",
} as const;

export const faqItems = [
  {
    question: "What is Call Bot?",
    answer:
      "Call Bot is a multi-tenant AI phone platform. It answers inbound calls, gathers details, books appointments when slots are available, can hand off to a human, and keeps records in your CRM, dispatch, and Ops console.",
  },
  {
    question: "Who is Call Bot for?",
    answer:
      "Call Bot fits field-service trades, clinics, restaurants, sales and support desks, insurance intake, and other businesses that need reliable phone coverage without missing revenue.",
  },
  {
    question: "What is the agent marketplace?",
    answer:
      "The marketplace offers one-click industry agent installs — HVAC, medical, restaurant, sales, support, collections, and more — with starter prompts and knowledge you can customize after install.",
  },
  {
    question: "Can I run more than one agent?",
    answer:
      "Yes. Create multiple agent profiles per tenant and assign each phone number to the right profile — reception, sales, support, or custom.",
  },
  {
    question: "Can Call Bot book appointments?",
    answer:
      "Yes. After identifying the caller and confirming details, Call Bot can offer real availability and book, reschedule, or cancel visits — it does not invent open times.",
  },
  {
    question: "What ops tools are included?",
    answer:
      "Ops includes live calls, a supervisor snapshot, quality reviews, a handoff follow-up queue, automations, team seats, usage metering, API keys, and white-label branding.",
  },
  {
    question: "Does each business keep its own data?",
    answer:
      "Yes. Call Bot is multi-tenant. Customers, appointments, knowledge, and assistant settings are scoped to the resolved business so data never mixes across companies.",
  },
  {
    question: "Is there a public API?",
    answer:
      "Yes. Tenant admins can issue API keys for read access to customers and calls via the /v1 endpoints. Automations can also POST signed HTTPS webhooks to your systems.",
  },
  {
    question: "How do I get started?",
    answer:
      "View pricing, create a workspace, and finish Stripe Checkout. Once Ops opens, install an agent from the marketplace, connect a number, and try the browser voice demo.",
  },
] as const;
