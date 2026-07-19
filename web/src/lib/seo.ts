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
  title: "Call Bot | AI Voice Assistant for Field Service Calls",
  titleTemplate: "%s | Call Bot",
  description:
    "Call Bot is an AI phone receptionist for HVAC, plumbing, electrical, and field-service businesses. Answer every call, capture job details, book appointments, hand off to humans, and sync with dispatch — in your brand’s voice.",
  keywords: [
    "AI phone receptionist",
    "AI voice assistant for business",
    "AI answering service for contractors",
    "field service answering service",
    "HVAC call answering AI",
    "HVAC after hours answering service",
    "plumbing appointment booking AI",
    "electrical service call intake",
    "automated service call intake",
    "AI dispatch phone agent",
    "missed call recovery field service",
    "voice AI scheduling",
    "ServiceTitan alternative voice AI",
    "multi-tenant voice agent",
    "SIP telephony voice AI",
    "LiveKit voice agent field service",
    "AI receptionist that books appointments",
    "Call Bot",
  ],
  locale: "en_US",
  ogImageAlt: "Call Bot — AI voice assistant that answers field-service calls",
  twitterHandle: "",
} as const;

export const faqItems = [
  {
    question: "What is Call Bot?",
    answer:
      "Call Bot is an AI voice assistant for field-service businesses. It answers inbound calls, gathers job details, books appointments when slots are available, can hand off to a human, and keeps records in your tenant’s CRM and dispatch tools.",
  },
  {
    question: "Who is Call Bot for?",
    answer:
      "Call Bot is built for HVAC, plumbing, electrical, and other multi-tenant field-service companies that need reliable after-hours and busy-hour call intake without missing revenue.",
  },
  {
    question: "How is Call Bot different from a generic chatbot?",
    answer:
      "Call Bot is voice-first and tenant-aware. It loads your approved Agent Profile, uses real scheduling and CRM tools, confirms before changing appointments, and never invents availability or prices.",
  },
  {
    question: "Can Call Bot book appointments?",
    answer:
      "Yes. After identifying the caller and confirming details, Call Bot can offer real availability and book, reschedule, or cancel visits through your scheduling system — it does not invent open times.",
  },
  {
    question: "Does each business keep its own data?",
    answer:
      "Yes. Call Bot is multi-tenant. Customers, appointments, knowledge articles, and assistant settings are scoped to the resolved business tenant so data never mixes across companies.",
  },
  {
    question: "What happens if the caller needs a person?",
    answer:
      "For emergencies, billing disputes, abuse, or an explicit request for a human, Call Bot can request a warm or cold transfer. If transfer is unavailable, it takes a callback number and saves a lead.",
  },
  {
    question: "Can I customize the greeting and tone?",
    answer:
      "Yes. Tenant admins edit the Agent Profile in ops — assistant name, greeting, tone, languages, hours summary, booking rules, restricted topics, and custom instructions — without exposing system prompts.",
  },
  {
    question: "Does Call Bot work with phone numbers?",
    answer:
      "Yes. After browser audio is stable, you can connect telephony so SIP callers reach the same voice agent. Tenant resolution uses trusted DID and trunk mapping, not caller free text.",
  },
  {
    question: "How do I try Call Bot?",
    answer:
      "Start with the browser voice demo to hear the assistant. Configure your Agent Profile in ops, then connect phone numbers through the telephony setup when you are ready for live callers.",
  },
] as const;
