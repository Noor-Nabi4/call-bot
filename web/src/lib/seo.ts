/** SEO configuration for the Call & Flow marketing site. */

export function getSiteUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
    process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim() ||
    process.env.VERCEL_URL?.trim() ||
    "http://localhost:3002";
  const withProtocol = raw.startsWith("http") ? raw : `https://${raw}`;
  return withProtocol.replace(/\/$/, "");
}

export function absoluteUrl(path = "/"): string {
  const base = getSiteUrl();
  if (!path || path === "/") return base;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export const seo = {
  brand: "Call & Flow",
  title: "AI Voice Agents & AI Receptionist for Businesses | Call & Flow",
  titleTemplate: "%s | Call & Flow",
  description:
    "AI voice agents that answer calls, book appointments, qualify leads, answer questions, and connect callers with your team. Automate business calls with Call & Flow.",
  keywords: [
    "AI voice agents",
    "AI voice agent",
    "AI phone agent",
    "AI receptionist",
    "AI answering service",
    "AI customer service agent",
    "AI appointment booking",
    "AI call answering",
    "business phone automation",
    "Call & Flow",
    "Call and Flow",
  ],
  locale: "en_US",
  ogImageAlt:
    "Call & Flow — AI voice agents and AI receptionist for US businesses",
  twitterHandle: "",
} as const;

export const faqItems = [
  {
    question: "What is an AI receptionist?",
    answer:
      "An AI receptionist is a voice agent that answers your business phone, greets callers, answers common questions, books appointments, captures lead details, and can transfer urgent calls to a person on your team.",
  },
  {
    question: "How does an AI voice agent work?",
    answer:
      "Call & Flow connects to your business phone line, listens to the caller, uses your knowledge base and booking rules to respond, and can hand off to a human when the conversation needs a person.",
  },
  {
    question: "Can AI answer business phone calls?",
    answer:
      "Yes. Call & Flow AI voice agents answer inbound calls for service businesses and call centers, including after-hours coverage when your team is busy or offline.",
  },
  {
    question: "Can an AI receptionist book appointments?",
    answer:
      "Yes. Agents can check availability, confirm caller details, and create appointments your team can trust — without inventing open times.",
  },
  {
    question: "Can AI transfer calls to a human?",
    answer:
      "Yes. When a caller needs a person, Call & Flow supports human handoff. If a live transfer is unavailable, it can take a callback request and queue follow-up with context.",
  },
  {
    question: "Can AI answer calls after business hours?",
    answer:
      "Yes. After-hours answering is a core use case — capture emergencies, book next-day appointments, answer FAQs, and make sure overnight leads are not lost.",
  },
  {
    question: "How much does an AI receptionist cost?",
    answer:
      "Call & Flow plans start with Starter and scale by included voice minutes, concurrent calls, phone numbers, users, and knowledge documents. See the pricing page for current plan details and overage rates.",
  },
  {
    question: "What businesses can use AI voice agents?",
    answer:
      "Home services, healthcare, dental, legal, real estate, restaurants, insurance, call centers, and other teams that cannot afford to miss the phone.",
  },
] as const;
