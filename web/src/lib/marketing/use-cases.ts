/** Distinct use-case landing content. */

export type UseCasePage = {
  slug: string;
  name: string;
  navLabel: string;
  title: string;
  description: string;
  h1: string;
  eyebrow: string;
  supporting: string;
  problems: readonly { title: string; body: string }[];
  capabilities: readonly { title: string; body: string }[];
  outcomes: readonly { title: string; body: string }[];
  faqs: readonly { question: string; answer: string }[];
  relatedIndustries: readonly string[];
  relatedUseCases: readonly string[];
  keywords: readonly string[];
};

export const useCasesHub = {
  title: "AI Voice Agent Use Cases for Business Phone Calls",
  description:
    "Explore Call & Flow AI voice-agent use cases: appointment booking, lead qualification, customer support, call answering, and inbound sales calls.",
  h1: "AI Voice Agent Use Cases",
  supporting:
    "Different calls need different outcomes. Start from the workflow your business cares about most — booking, qualification, support, always-on answering, or inbound sales — then connect it to your industry template and handoff rules.",
} as const;

export const useCasePages: readonly UseCasePage[] = [
  {
    slug: "appointment-booking",
    name: "Appointment Booking",
    navLabel: "Appointment Booking",
    title: "AI Appointment Booking by Phone",
    description:
      "AI appointment booking by phone that offers real availability, confirms caller details, and schedules visits during inbound business calls.",
    h1: "AI Appointment Booking by Phone",
    eyebrow: "Use case",
    supporting:
      "Stop promising callbacks for scheduling. Call & Flow checks availability, confirms the details that matter, and books appointments your team can trust.",
    problems: [
      {
        title: "Callers hang up before a human books them",
        body: "If the front desk is busy, scheduling intent dies in voicemail or a vague “we’ll call you back.”",
      },
      {
        title: "Double-books and invented times",
        body: "Teams need booking that respects real capacity — not optimistic guesses from a chatbot.",
      },
      {
        title: "After-hours demand has nowhere to go",
        body: "Night and weekend callers still want a slot on the calendar for tomorrow.",
      },
    ],
    capabilities: [
      {
        title: "Offer real availability",
        body: "Present open windows based on the booking rules configured in your workspace.",
      },
      {
        title: "Confirm critical details",
        body: "Name, phone, service type, and notes are verified before the appointment is saved.",
      },
      {
        title: "Reschedule and cancel flows",
        body: "Existing appointments can be adjusted through the conversational flows you enable.",
      },
      {
        title: "Human backup",
        body: "When booking rules cannot satisfy the request, escalate or queue a callback with context.",
      },
    ],
    outcomes: [
      {
        title: "More completed bookings per answered call",
        body: "Scheduling intent converts while the caller is still on the line.",
      },
      {
        title: "Cleaner calendars",
        body: "Appointments arrive with the fields your ops team actually uses.",
      },
      {
        title: "Coverage beyond office hours",
        body: "After-hours callers can still leave with a confirmed next step.",
      },
    ],
    faqs: [
      {
        question: "Can an AI receptionist book appointments?",
        answer:
          "Yes. Call & Flow can check availability, confirm details, and create appointments according to your rules.",
      },
      {
        question: "Will it invent open times?",
        answer:
          "No. Booking should reflect configured availability. If a slot cannot be offered, the agent takes a follow-up action you define.",
      },
      {
        question: "Which businesses use AI appointment booking?",
        answer:
          "Home services, dental, healthcare clinics, legal consults, real estate showings, and other appointment-driven teams.",
      },
    ],
    relatedIndustries: ["hvac", "dental", "healthcare", "real-estate"],
    relatedUseCases: ["call-answering", "lead-qualification", "customer-support"],
    keywords: [
      "AI appointment booking",
      "AI receptionist booking",
      "book appointments by phone AI",
    ],
  },
  {
    slug: "lead-qualification",
    name: "Lead Qualification",
    navLabel: "Lead Qualification",
    title: "AI Lead Qualification by Phone",
    description:
      "AI lead qualification by phone that asks discovery questions, captures contact details, and routes sales-ready callers to your team while interest is high.",
    h1: "AI Lead Qualification by Phone",
    eyebrow: "Use case",
    supporting:
      "Every inbound marketing dollar depends on speed-to-lead. Call & Flow asks your discovery questions, scores fit based on your rules, and books the next conversation.",
    problems: [
      {
        title: "Speed-to-lead is too slow",
        body: "By the time sales dials back, the prospect already booked a competitor.",
      },
      {
        title: "Unqualified demos waste calendar time",
        body: "Reps need basic filters — budget band, timeline, service area, intent — before a meeting.",
      },
      {
        title: "Notes are inconsistent",
        body: "Half-captured voicemails force SDRs to re-qualify from scratch.",
      },
    ],
    capabilities: [
      {
        title: "Structured discovery",
        body: "Ask the exact qualification questions your sales process requires.",
      },
      {
        title: "Contact capture",
        body: "Collect name, phone, email, and company details before the caller hangs up.",
      },
      {
        title: "Route by intent",
        body: "Send hot leads to sales, nurture paths to follow-up, and support intents elsewhere.",
      },
      {
        title: "Book the next step",
        body: "Offer a demo, estimate, or consult slot while motivation is highest.",
      },
    ],
    outcomes: [
      {
        title: "Higher connect-to-meeting rate",
        body: "Qualified prospects leave with a scheduled conversation.",
      },
      {
        title: "Cleaner pipeline handoff",
        body: "Reps start with answers, not detective work.",
      },
      {
        title: "Better use of ad spend",
        body: "Paid calls are answered and worked immediately.",
      },
    ],
    faqs: [
      {
        question: "Can AI qualify leads on a phone call?",
        answer:
          "Yes. Configure the questions that define a sales-ready lead and Call & Flow will collect them conversationally.",
      },
      {
        question: "Can it transfer hot leads to a human?",
        answer:
          "Yes. When a live transfer is available, urgent or high-intent callers can be handed off with context.",
      },
      {
        question: "Does this replace SDRs?",
        answer:
          "It handles first-response qualification and booking so SDRs and AEs spend time on conversations that already cleared the basics.",
      },
    ],
    relatedIndustries: ["roofing", "real-estate", "legal", "insurance"],
    relatedUseCases: ["sales-calls", "appointment-booking", "call-answering"],
    keywords: [
      "AI lead qualification",
      "AI sales phone agent",
      "qualify leads with AI voice",
    ],
  },
  {
    slug: "customer-support",
    name: "Customer Support",
    navLabel: "Customer Support",
    title: "AI Customer Support Voice Agent",
    description:
      "AI customer support voice agent that answers FAQs from your knowledge base, opens follow-ups, and escalates account issues to humans with context.",
    h1: "AI Customer Support Voice Agent",
    eyebrow: "Use case",
    supporting:
      "Support queues fill with questions you have already documented. Call & Flow answers from your knowledge base, creates follow-ups when needed, and escalates account issues cleanly.",
    problems: [
      {
        title: "Repetitive FAQs burn agent time",
        body: "Hours, policies, and how-to questions do not always need a live seat.",
      },
      {
        title: "Ungrounded answers create risk",
        body: "Support automation must stick to approved documents — inventing policy is worse than a hold queue.",
      },
      {
        title: "Callers hate repeating themselves",
        body: "When escalation happens, the human should already know what was tried.",
      },
    ],
    capabilities: [
      {
        title: "Knowledge-grounded answers",
        body: "Resolve FAQs from documents you approve and keep updated.",
      },
      {
        title: "Follow-up creation",
        body: "Open tickets or callback tasks when the issue needs offline work.",
      },
      {
        title: "Context-rich handoff",
        body: "Transfer to humans with a summary of the conversation so far.",
      },
      {
        title: "After-hours support coverage",
        body: "Keep answering when the support floor is closed or thinly staffed.",
      },
    ],
    outcomes: [
      {
        title: "Higher containment on simple issues",
        body: "Documented questions resolve without waiting for a live agent.",
      },
      {
        title: "Safer automation",
        body: "Answers stay tied to your knowledge instead of freeform invention.",
      },
      {
        title: "Shorter escalated handle time",
        body: "Humans pick up mid-conversation with context already attached.",
      },
    ],
    faqs: [
      {
        question: "Can AI answer customer service calls?",
        answer:
          "Yes. Call & Flow support agents handle inbound voice questions using your knowledge base and escalation rules.",
      },
      {
        question: "What if the AI does not know the answer?",
        answer:
          "It should say so, avoid inventing policy, and either take a message or transfer to a human.",
      },
      {
        question: "Can it work alongside our call center?",
        answer:
          "Yes. Many teams use AI for FAQ containment and overflow while live agents handle exceptions.",
      },
    ],
    relatedIndustries: ["call-centers", "insurance", "healthcare", "home-services"],
    relatedUseCases: ["call-answering", "appointment-booking", "sales-calls"],
    keywords: [
      "AI customer support voice agent",
      "AI voice customer service",
      "AI phone customer support",
    ],
  },
  {
    slug: "call-answering",
    name: "Call Answering",
    navLabel: "Call Answering",
    title: "AI Call Answering Service for Businesses",
    description:
      "AI call answering service that covers overflow and after-hours rings, greets callers in your brand voice, captures intent, and routes the next business action.",
    h1: "AI Call Answering When Your Team Cannot Pick Up",
    eyebrow: "Use case",
    supporting:
      "This workflow is about never missing the ring — lunch rushes, campaign spikes, and nights when nobody is free. Call & Flow answers, captures why they called, and completes the next step or queues a human follow-up.",
    problems: [
      {
        title: "Voicemail is a conversion dead end",
        body: "Most callers will not leave a detailed message, and many never call back.",
      },
      {
        title: "Overflow during peaks",
        body: "Campaigns, storms, and lunch rushes create more rings than people.",
      },
      {
        title: "After-hours black holes",
        body: "You pay for ads that ring into silence after 5pm.",
      },
    ],
    capabilities: [
      {
        title: "Always-on greeting",
        body: "Answer in your brand voice with a clear path for the caller’s intent.",
      },
      {
        title: "Intent capture",
        body: "Understand whether the caller needs booking, support, sales, or a person.",
      },
      {
        title: "Message taking with structure",
        body: "When a human is unavailable, capture useful details instead of a vague callback note.",
      },
      {
        title: "After-hours playbooks",
        body: "Different rules for nights, weekends, and holidays — including emergency escalation.",
      },
    ],
    outcomes: [
      {
        title: "Fewer abandoned opportunities",
        body: "Callers reach a helpful conversation on the first try.",
      },
      {
        title: "Consistent front-door experience",
        body: "Every line gets the same professional standard.",
      },
      {
        title: "Operational calm",
        body: "Staff stop sprinting to every ring while mid-task.",
      },
    ],
    faqs: [
      {
        question: "Can AI answer business phone calls?",
        answer:
          "Yes. Call & Flow AI voice agents answer inbound business lines and follow the workflows you configure.",
      },
      {
        question: "Is this an AI answering service?",
        answer:
          "It functions as a modern AI answering and receptionist service — with booking, qualification, and human handoff built in.",
      },
      {
        question: "Can it cover multiple phone numbers?",
        answer:
          "Yes. Plans include phone number limits, and you can configure different agents or scripts per line.",
      },
    ],
    relatedIndustries: ["home-services", "restaurants", "dental", "call-centers"],
    relatedUseCases: [
      "appointment-booking",
      "lead-qualification",
      "customer-support",
    ],
    keywords: [
      "AI call answering",
      "AI answering service",
      "AI phone answering for business",
    ],
  },
  {
    slug: "sales-calls",
    name: "Sales Calls",
    navLabel: "Sales Calls",
    title: "AI Sales Voice Agent for Inbound Phone Opportunities",
    description:
      "AI sales voice agent that greets inbound opportunities, runs discovery, books demos or estimates, and hands hot leads to closers with context.",
    h1: "AI Sales Voice Agent for Inbound Opportunities",
    eyebrow: "Use case",
    supporting:
      "Unlike a general voice-agent platform overview, this use case focuses on inbound sales moments: capture interest, ask the discovery questions your reps need, and book the next conversation before the caller moves on.",
    problems: [
      {
        title: "Inbound calls hit when reps are busy",
        body: "A live opportunity becomes a voicemail while the team is already on demos.",
      },
      {
        title: "First response is inconsistent",
        body: "Different people ask different questions, so CRM quality varies.",
      },
      {
        title: "Hot leads wait for scheduling",
        body: "Even interested buyers bounce when booking a next step takes another day.",
      },
    ],
    capabilities: [
      {
        title: "Sales-ready greeting",
        body: "Open with brand-appropriate energy and a clear path to value.",
      },
      {
        title: "Discovery + capture",
        body: "Run your qualification script and store the answers for the closer.",
      },
      {
        title: "Demo / estimate booking",
        body: "Convert interest into a calendar event while the caller is engaged.",
      },
      {
        title: "Live transfer for closers",
        body: "When a human should take over immediately, hand off with context.",
      },
    ],
    outcomes: [
      {
        title: "More demos from the same ad spend",
        body: "Inbound calls complete a next step instead of dying unanswered.",
      },
      {
        title: "Rep time on closable conversations",
        body: "Humans join after basics are already collected.",
      },
      {
        title: "Consistent pipeline data",
        body: "Every sales call gathers the same critical fields.",
      },
    ],
    faqs: [
      {
        question: "Can AI handle inbound sales calls?",
        answer:
          "Yes. Configure a sales-oriented agent to qualify, capture, and book — then escalate when a closer should join.",
      },
      {
        question: "Does Call & Flow do cold outbound calling?",
        answer:
          "Call & Flow focuses on reliable inbound voice workflows and configured outbound use where your workspace supports it. Start with inbound capture and booking for the fastest ROI.",
      },
      {
        question: "Which industries use AI sales phone agents?",
        answer:
          "Roofing, real estate, home services, legal intake, insurance quotes, and other high-intent inbound phone businesses.",
      },
    ],
    relatedIndustries: ["roofing", "real-estate", "insurance", "legal"],
    relatedUseCases: [
      "lead-qualification",
      "appointment-booking",
      "call-answering",
    ],
    keywords: [
      "AI sales voice agent",
      "AI sales calls",
      "inbound sales voice AI",
      "AI phone sales automation",
    ],
  },
] as const;

export function getUseCase(slug: string): UseCasePage | undefined {
  return useCasePages.find((page) => page.slug === slug);
}

export function getUseCaseSlugs(): string[] {
  return useCasePages.map((page) => page.slug);
}
