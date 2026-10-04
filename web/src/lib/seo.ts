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
    question: "What can Call & Flow AI voice agents do?",
    answer:
      "They answer inbound business calls, follow your configured workflows, book appointments, qualify leads, answer approved FAQs, and hand off to a person when a human is needed.",
  },
  {
    question: "How does an AI voice agent work on a live call?",
    answer:
      "Call & Flow connects to your business phone line, understands why the caller reached out, uses your knowledge and booking rules to respond, and can escalate with context when the conversation needs your team.",
  },
  {
    question: "Is an AI receptionist the same as an AI voice agent?",
    answer:
      "An AI receptionist is a common role for a voice agent — focused on front-desk answering. The same platform can also power support, sales, and specialized intake workflows.",
  },
  {
    question: "Can AI book appointments during the call?",
    answer:
      "Yes. Agents can offer real availability, confirm caller details, and schedule visits without inventing open times.",
  },
  {
    question: "Can AI transfer calls to a human?",
    answer:
      "Yes. When a caller needs a person, Call & Flow supports human handoff. If a live transfer is unavailable, it can take a callback request and queue follow-up with notes attached.",
  },
  {
    question: "Can AI cover nights and weekends?",
    answer:
      "Yes. After-hours coverage is a core reason teams adopt AI call answering — capture emergencies, book next-day appointments, and keep overnight leads from going to voicemail.",
  },
  {
    question: "How is Call & Flow priced?",
    answer:
      "Plans scale by included voice minutes, concurrent calls, phone numbers, users, and knowledge limits. See the pricing page for current Starter, Growth, Pro, and Enterprise details.",
  },
  {
    question: "Which businesses use AI voice agents?",
    answer:
      "Home services, healthcare, dental, legal, real estate, restaurants, insurance, call centers, and other teams that cannot afford to miss the phone.",
  },
] as const;
