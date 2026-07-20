/** SEO configuration for the CallBot marketing site. */

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
  brand: "CallBot",
  title: "CallBot | AI Voice Platform for Growing Businesses",
  titleTemplate: "%s | CallBot",
  description:
    "CallBot is an AI voice platform for businesses and call centers. Deploy AI receptionists, support agents, and sales agents that book appointments, answer from your knowledge base, and hand off to humans.",
  keywords: [
    "AI voice platform",
    "AI phone receptionist",
    "AI customer support agent",
    "AI sales agent",
    "AI answering service",
    "appointment booking AI",
    "call center automation",
    "human handoff voice AI",
    "multi-tenant voice platform",
    "knowledge base phone agent",
    "AI receptionist for healthcare",
    "AI answering for home services",
    "restaurant reservation AI",
    "CallBot",
  ],
  locale: "en_US",
  ogImageAlt: "CallBot — AI voice platform for businesses and call centers",
  twitterHandle: "",
} as const;

export const faqItems = [
  {
    question: "What is CallBot?",
    answer:
      "CallBot is an AI voice platform for businesses and call centers. It answers inbound calls, books appointments, responds from your knowledge base, and hands off to humans when needed — all from a multi-tenant workspace.",
  },
  {
    question: "Who is CallBot for?",
    answer:
      "CallBot fits service businesses, healthcare, legal, insurance, real estate, restaurants, home services, call centers, and other teams that cannot afford to miss the phone.",
  },
  {
    question: "What can AI voice agents do?",
    answer:
      "Agents can act as receptionists, customer support, or sales specialists — answering FAQs, capturing lead details, booking appointments, and escalating complex or sensitive requests.",
  },
  {
    question: "Can CallBot book appointments?",
    answer:
      "Yes. After confirming caller details, CallBot can offer real availability and book, reschedule, or cancel visits. It does not invent open times.",
  },
  {
    question: "What happens when a caller needs a person?",
    answer:
      "CallBot supports human handoff. When transfer is available, the call moves to your team with context. If not, CallBot can take a callback request and queue follow-up.",
  },
  {
    question: "How does the knowledge base work?",
    answer:
      "You upload approved documents and FAQs. Agents use that content to answer questions accurately and stay within your business policies.",
  },
  {
    question: "Is CallBot multi-tenant?",
    answer:
      "Yes. Each business keeps isolated numbers, agents, customers, appointments, and knowledge so data never mixes across companies.",
  },
  {
    question: "Can I run more than one agent?",
    answer:
      "Yes. Create multiple agent profiles — reception, support, sales, or custom — and assign each phone number to the right profile.",
  },
  {
    question: "How do I get started?",
    answer:
      "Start a free trial, create your workspace, configure an agent, and connect a phone number. You can also book a demo if you want a guided walkthrough.",
  },
] as const;
