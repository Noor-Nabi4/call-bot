/** Site copy for the Call Bot marketing landing. */

export const site = {
  brand: "Call Bot",
  title: "Call Bot | AI Voice Assistant for Field Service Calls",
  description:
    "Call Bot is an AI phone receptionist for HVAC, plumbing, electrical, and field-service businesses. Answer every call, capture job details, book appointments, hand off when needed, and sync with dispatch — in your brand’s voice.",
} as const;

export const hero = {
  brand: "Call Bot",
  headline: "Never miss another service call.",
  supporting:
    "An AI voice assistant that answers for your business, takes the job details, and books the visit.",
  primaryCta: "Try a live demo",
  secondaryCta: "Open dispatch",
} as const;

export const answer = {
  title: "Answer every call like your best coordinator.",
  body: "Callers get a natural conversation in your business voice — hours, service area, and next steps — without waiting on hold or hearing a generic answering machine.",
} as const;

export const book = {
  title: "Turn conversations into booked work.",
  body: "Capture the customer, save the request, and offer real appointment slots. Dispatch sees the same records your team already uses — no retyping from voicemail.",
} as const;

export const howItWorks = {
  title: "How Call Bot works",
  supporting:
    "From the first ring to a booked job, every step stays inside your tenant’s data.",
  steps: [
    {
      title: "Call comes in",
      body: "Browser or phone. Call Bot resolves the business from trusted telephony or room metadata — never from free-form caller guesses.",
    },
    {
      title: "Conversation starts",
      body: "Your tenant Agent Profile loads: greeting, tone, hours, service areas, and language preferences. Replies stay short and human.",
    },
    {
      title: "Details get saved",
      body: "Customer lookup, lead capture, knowledge answers, and booking tools run only for that tenant. Critical actions ask for confirmation first.",
    },
    {
      title: "Team stays in sync",
      body: "Ops dispatch, knowledge, and handoff settings use the same platform records your coordinators and technicians already open.",
    },
  ],
} as const;

export const capabilities = {
  title: "What the assistant can handle",
  supporting:
    "Built for real field-service intake — not a generic chatbot pasted onto a phone line.",
  items: [
    {
      title: "Voice intake",
      body: "Greet callers, ask one question at a time, and collect name, phone, address, and service need.",
    },
    {
      title: "CRM records",
      body: "Look up customers by phone, create or update profiles, and open leads with reference codes.",
    },
    {
      title: "Scheduling",
      body: "Check live availability, offer a few real slots, then book, reschedule, or cancel with confirmation.",
    },
    {
      title: "Business knowledge",
      body: "Answer FAQs from your curated articles without inventing prices, policies, or coverage.",
    },
    {
      title: "Human handoff",
      body: "Transfer to a live teammate for emergencies, billing disputes, or when the caller asks for a person.",
    },
    {
      title: "Tenant isolation",
      body: "Every tool and transcript path is scoped to the resolved business. Profiles and knowledge never cross tenants.",
    },
  ],
} as const;

export const industries = {
  title: "Built for field-service trades",
  supporting:
    "Same platform, separate tenants — each company keeps its own phone numbers, customers, and assistant settings.",
  items: [
    {
      name: "HVAC",
      body: "Heating and cooling repair intake, emergency triage language, and weekday booking windows.",
    },
    {
      name: "Plumbing",
      body: "Leak and drain calls, service-area checks, and appointment capture when crews are booked solid.",
    },
    {
      name: "Electrical",
      body: "Panel and outlet requests with clear handoff rules for unsafe or urgent situations.",
    },
    {
      name: "General contractors",
      body: "Multi-trade service desks that need one answering layer and many tenant brands behind it.",
    },
  ],
} as const;

export const handoff = {
  title: "Escalate when a human should take over.",
  body: "Billing fights, emergencies, and frustrated callers can transfer to your team. If transfer is unavailable, Call Bot takes a callback and saves the request.",
} as const;

export const close = {
  title: "Ready for your next busy season?",
  body: "Start with a browser demo, configure your assistant profile, then connect phone numbers when you’re ready for live callers.",
  primaryCta: "Start the demo",
  secondaryCta: "Sign in to ops",
} as const;

export const footer = {
  note: "Multi-tenant field service voice AI — HVAC, plumbing, electrical, and more.",
  links: [
    { label: "Voice demo", hrefEnv: "playground" as const },
    { label: "Dispatch ops", hrefEnv: "ops" as const },
    { label: "Sign in", hrefEnv: "login" as const },
  ],
} as const;
