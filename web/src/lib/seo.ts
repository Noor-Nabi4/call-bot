/** SEO configuration for the VoxPilot marketing site. */

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
  brand: "VoxPilot",
  title: "VoxPilot | AI Voice Platform for Service Businesses & Call Centers",
  titleTemplate: "%s | VoxPilot",
  description:
    "VoxPilot is an AI voice platform for service businesses and call centers. Deploy AI receptionists, support agents, and sales agents that book appointments, answer from your knowledge base, and hand off to humans.",
  keywords: [
    "AI voice platform",
    "AI phone receptionist",
    "AI customer support agent",
    "AI sales agent",
    "call center automation",
    "appointment booking AI",
    "human handoff voice AI",
    "multi-tenant voice platform",
    "service business phone AI",
    "VoxPilot",
  ],
  locale: "en_US",
  ogImageAlt:
    "VoxPilot — AI voice platform for service businesses and call centers",
  twitterHandle: "",
} as const;

export const faqItems = [
  {
    question: "What is VoxPilot?",
    answer:
      "VoxPilot is an AI voice platform for service businesses and call centers. It answers inbound calls, books appointments, responds from your knowledge base, and hands off to humans when needed.",
  },
  {
    question: "Who is VoxPilot for?",
    answer:
      "VoxPilot fits home and field services, healthcare, legal, insurance, real estate, restaurants, call centers, and other teams that cannot afford to miss the phone.",
  },
  {
    question: "Can I try it before signing up?",
    answer:
      "Yes. Use the live browser voice demo on this page to talk to an AI agent, then start a free trial when you are ready.",
  },
  {
    question: "What can AI voice agents do?",
    answer:
      "Agents can act as receptionists, customer support, or sales specialists — answering FAQs, capturing lead details, booking appointments, and escalating complex requests.",
  },
  {
    question: "Are there industry templates?",
    answer:
      "Yes. Start from templates for common service industries, then customize greeting, knowledge, booking rules, and handoff preferences for your business.",
  },
  {
    question: "What happens when a caller needs a person?",
    answer:
      "VoxPilot supports human handoff. When transfer is available, the call moves to your team with context. If not, VoxPilot can take a callback request and queue follow-up.",
  },
  {
    question: "Is VoxPilot multi-tenant?",
    answer:
      "Yes. Each business keeps isolated numbers, agents, customers, appointments, and knowledge so data never mixes across companies.",
  },
  {
    question: "How do I get started?",
    answer:
      "Try the voice demo, start a free trial, create your workspace, configure an agent from a template, and connect a phone number.",
  },
] as const;
