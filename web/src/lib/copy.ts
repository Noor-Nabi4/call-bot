/** Site copy for the Call Bot marketing landing. */

export const site = {
  brand: "Call Bot",
  title: "Call Bot | AI Phone Agents for Growing Businesses",
  description:
    "Call Bot answers every call in your brand’s voice, books appointments, hands off to humans, and runs multi-tenant ops — with marketplace agents, live monitoring, and a public API.",
} as const;

export const hero = {
  brand: "Call Bot",
  headline: "Your AI phone team, ready in minutes.",
  supporting:
    "Install an industry agent, connect a number, and answer every call — booking, intake, and handoff included.",
  primaryCta: "Try a live demo",
  secondaryCta: "View pricing",
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
    "From marketplace install to a live call, every step stays inside your tenant’s data.",
  steps: [
    {
      title: "Install an agent",
      body: "Pick a ready-made industry template from the marketplace — HVAC, medical, restaurant, sales, support, and more — or start custom.",
    },
    {
      title: "Connect your number",
      body: "Buy or connect a phone line. Call Bot resolves the business from trusted telephony metadata — never from free-form caller guesses.",
    },
    {
      title: "Shape the conversation",
      body: "Tune greeting, call flow steps, tools, and knowledge. Replies stay short, tenant-scoped, and confirmation-gated for bookings.",
    },
    {
      title: "Run ops in one place",
      body: "Live calls, supervisor view, handoff queue, quality scores, and dispatch use the same platform records your team already opens.",
    },
  ],
} as const;

export const capabilities = {
  title: "What the platform includes",
  supporting:
    "Voice AI plus the operations layer — not a chatbot taped onto a phone line.",
  items: [
    {
      title: "Marketplace agents",
      body: "One-click industry installs with starter knowledge, prompts, and tool presets you can customize after.",
    },
    {
      title: "Multi-profile routing",
      body: "Run reception, sales, and support agents under one tenant. Assign each phone number to the right profile.",
    },
    {
      title: "Scheduling & CRM",
      body: "Look up customers, open leads, and book real availability — never invented slots or prices.",
    },
    {
      title: "Call center ops",
      body: "Live monitoring, supervisor snapshot, quality reviews, and a handoff follow-up queue for your team.",
    },
    {
      title: "Automations & webhooks",
      body: "React to call ended, handoff, or booking events — write audits, create jobs, or POST signed HTTPS webhooks.",
    },
    {
      title: "Public API & branding",
      body: "Issue API keys for customers and calls, and white-label Ops with your product name, logo, and colors.",
    },
  ],
} as const;

export const industries = {
  title: "Ready for your industry",
  supporting:
    "Same multi-tenant platform — install a template, keep your own numbers, customers, and knowledge.",
  items: [
    {
      name: "Field service",
      body: "HVAC, plumbing, and electrical intake with emergency language, service-area checks, and weekday booking windows.",
    },
    {
      name: "Healthcare & hospitality",
      body: "Clinic front desk and restaurant reservations — schedule politely without inventing clinical or menu advice.",
    },
    {
      name: "Sales & support",
      body: "Qualify leads, answer FAQs, triage tickets, and escalate billing or supervisor requests cleanly.",
    },
    {
      name: "Insurance & collections",
      body: "Policy intake, claims routing, and respectful payment reminders with clear human handoff rules.",
    },
  ],
} as const;

export const platform = {
  title: "Built for operators, not demos.",
  supporting:
    "Everything your coordinators need after the call starts — without leaving Ops.",
  items: [
    {
      title: "Live & supervisor",
      body: "See active calls, open handoffs, and today’s volume. Quality-score ended conversations from the call drawer.",
    },
    {
      title: "Handoff queue",
      body: "When a call ends after a handoff request, it lands in a claimable follow-up queue for your team.",
    },
    {
      title: "Team & billing",
      body: "Invite seats, enforce plan limits, track voice minutes, and manage Stripe billing from the same console.",
    },
  ],
} as const;

export const handoff = {
  title: "Escalate when a human should take over.",
  body: "Billing fights, emergencies, and frustrated callers can transfer to your team. If transfer is unavailable, Call Bot takes a callback and saves the request.",
} as const;

export const close = {
  title: "Ready to answer the next call?",
  body: "Pick a plan, create your workspace, and finish checkout. Install an agent from the marketplace once Ops opens.",
  primaryCta: "View pricing",
  secondaryCta: "Sign in to ops",
} as const;

export const pricing = {
  brand: "Call Bot",
  title: "Voice minutes. Real ops. Clear limits.",
  supporting:
    "Pick the plan that matches your call volume and crew — not a seat count.",
  comparisonTitle: "At a glance",
  trialTitle: "Try before you connect a number",
  numbersTitle: "Phone numbers",
  addOnsTitle: "Add-ons",
  annualNote:
    "Pay annually and get about two months free: Starter $990 · Growth $2,490 · Pro $4,990.",
  note: "Plans activate after Stripe confirms payment. SaaS billing uses our platform Stripe account — separate from any future Connect payouts.",
  contactSalesHref: "mailto:sales@callbot.example?subject=Call%20Bot%20Enterprise",
  primaryCta: "Start with Growth",
} as const;

export const signup = {
  brand: "Call Bot",
  heading: "Open your workspace",
  supporting:
    "Create the business account, then finish payment in Stripe Checkout.",
  asideTitle: "Answer every call. Run the work.",
  asideBody:
    "Your plan unlocks after Stripe confirms the subscription — not on the success redirect.",
  businessName: "Business name",
  businessId: "Business ID",
  businessIdHint: "Used at sign-in. Lowercase, numbers, hyphens.",
  timezone: "Timezone",
  yourName: "Your name",
  email: "Work email",
  password: "Password",
  passwordHint: "At least 8 characters",
  plan: "Choose a plan",
  submit: "Continue to checkout",
  submitting: "Starting checkout…",
  failedTitle: "Could not start signup",
  failedMessage: "Check your details and try again.",
  canceled: "Checkout was canceled. Pick a plan and try again when you’re ready.",
  signIn: "Already have an account? Sign in",
  comparePlans: "Compare plans",
} as const;

export const footer = {
  note: "Multi-tenant voice AI — marketplace agents, call ops, and APIs for growing businesses.",
  links: [
    { label: "Pricing", hrefEnv: "pricing" as const },
    { label: "Voice demo", hrefEnv: "playground" as const },
    { label: "Ops console", hrefEnv: "ops" as const },
    { label: "Sign in", hrefEnv: "login" as const },
  ],
} as const;
