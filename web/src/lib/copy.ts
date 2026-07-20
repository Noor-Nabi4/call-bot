/** Site copy for the CallBot marketing landing. */

export const site = {
  brand: "CallBot",
  title: "CallBot | AI Voice Platform for Service Businesses & Call Centers",
  description:
    "CallBot is an AI voice platform for service businesses and call centers. Deploy AI receptionists, support agents, and sales agents that book appointments, answer from your knowledge base, and hand off to humans.",
} as const;

export const hero = {
  brand: "CallBot",
  eyebrow: "AI Voice Platform",
  headline: "Answer Every Call With AI",
  supporting:
    "The AI voice platform for service businesses and call centers. Deploy receptionists, support agents, and sales agents that book work, answer from your knowledge base, and hand off to humans.",
  primaryCta: "Start Free Trial",
  secondaryCta: "Try Voice Demo",
  trustItems: [
    "Service businesses & call centers",
    "Industry templates included",
    "Human handoff built in",
  ],
} as const;

export const voiceDemo = {
  title: "Talk to CallBot before you sign up",
  supporting:
    "Start a live browser call and hear how an AI voice agent greets callers, answers questions, and keeps the conversation moving.",
  sessionLabel: "Live voice demo",
  ready: "Ready when you are",
  connecting: "Connecting…",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  interrupted: "Interrupted",
  ended: "Call ended",
  connectionProblem: "Connection problem",
  idleHint:
    "Allow microphone access, then speak naturally. This is a live AI voice agent — not a recording.",
  waitingHint: "Say hello to start the conversation.",
  startCall: "Start voice demo",
  connectingAction: "Connecting…",
  endCall: "End call",
  startFailed: "We could not start the demo. Please try again.",
  interruptedError: "The call was interrupted. You can start again.",
  privacy: "Demo calls are short-lived and used only to show CallBot in action.",
  ctaAfter: "Like what you heard? Start a free trial.",
} as const;

export const features = {
  title: "Voice capabilities built for phone work",
  supporting:
    "Everything operators need after the phone rings — without stitching separate tools together.",
  items: [
    {
      tab: "Receptionist",
      badge: "Front desk",
      title: "AI Receptionist that never misses a call",
      body: "Greet callers in your brand voice, answer hours and service questions, and route by intent so your team stays focused.",
      previewLabel: "Live receptionist",
      previewLines: [
        "Greeting delivered",
        "Intent: schedule visit",
        "Routed to booking flow",
      ],
    },
    {
      tab: "Support",
      badge: "Help desk",
      title: "Support answers grounded in your knowledge",
      body: "Resolve FAQs from approved documents, open follow-ups when needed, and escalate account issues cleanly.",
      previewLabel: "Support agent",
      previewLines: [
        "Knowledge match found",
        "Answer confirmed",
        "Follow-up created",
      ],
    },
    {
      tab: "Sales",
      badge: "Lead desk",
      title: "Sales agents that qualify while interest is high",
      body: "Capture contact details, ask discovery questions, and book demos before the caller hangs up.",
      previewLabel: "Sales agent",
      previewLines: [
        "Lead captured",
        "Qualified: yes",
        "Demo slot offered",
      ],
    },
    {
      tab: "Booking",
      badge: "Scheduling",
      title: "Appointment booking inside the conversation",
      body: "Offer real availability, confirm details, and write bookings your team can trust — no invented times.",
      previewLabel: "Booking flow",
      previewLines: [
        "Availability checked",
        "Slot confirmed",
        "Appointment saved",
      ],
    },
    {
      tab: "Handoff",
      badge: "Human assist",
      title: "Human handoff with full call context",
      body: "When a caller needs a person, transfer or queue a callback so your team picks up knowing exactly what happened.",
      previewLabel: "Handoff queue",
      previewLines: [
        "Escalation requested",
        "Summary attached",
        "Agent notified",
      ],
    },
  ],
} as const;

/** @deprecated Use features — kept for JSON-LD howTo compatibility */
export const platform = features;

export const industries = {
  title: "Industry templates, ready to customize",
  supporting:
    "Start from a template built for how your callers talk — then keep your own numbers, knowledge, and branding.",
  items: [
    {
      name: "Home & field services",
      body: "Intake, emergency language, service-area checks, and estimate booking for trades and on-site teams.",
    },
    {
      name: "Healthcare & clinics",
      body: "Front-desk coverage for hours, routing, and scheduling — without inventing clinical advice.",
    },
    {
      name: "Legal & insurance",
      body: "Matter and claims intake, document requests, and clean escalation to the right desk.",
    },
    {
      name: "Real estate & hospitality",
      body: "Qualify inquiries, book showings or reservations, and capture details on the first call.",
    },
    {
      name: "Call centers",
      body: "Automate high-volume FAQs and overflow while supervisors keep full visibility.",
    },
    {
      name: "Restaurants & local retail",
      body: "Handle hours, location, and reservation questions when your team is mid-service.",
    },
  ],
} as const;

export const howItWorks = {
  title: "How CallBot works",
  supporting: "From signup to live answering in a few guided steps.",
  steps: [
    {
      title: "Create your workspace",
      body: "Open a CallBot account and invite the teammates who run the phones.",
    },
    {
      title: "Pick a template and configure",
      body: "Choose an industry template, then set greeting, knowledge, booking, and handoff rules.",
    },
    {
      title: "Connect a number and go live",
      body: "Point a business line at CallBot and monitor outcomes from one operations console.",
    },
  ],
} as const;

export const pricingPreview = {
  title: "Flexible pricing",
  supporting:
    "Pick the plan that matches your call volume — start with a trial, then scale minutes and numbers as you grow.",
  cta: "Start Free Trial",
  note: "Plans activate after checkout confirms. Minutes, concurrent calls, and numbers are included per plan.",
} as const;

export const faq = {
  title: "Frequently asked questions",
  supporting: "Straight answers about CallBot for service businesses and call centers.",
} as const;

export const close = {
  title: "Ready to answer every call?",
  body: "Start a free trial, configure your first voice agent, and put CallBot on a number your customers already dial.",
  primaryCta: "Start Free Trial",
  secondaryCta: "Try voice demo",
} as const;

export const pricing = {
  brand: "CallBot",
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
  contactSalesHref: "mailto:sales@callbot.example?subject=CallBot%20Enterprise",
  primaryCta: "Start with Growth",
} as const;

export const signup = {
  brand: "CallBot",
  heading: "Create your CallBot workspace",
  supporting:
    "A few details about your business, then choose a plan and finish checkout.",
  stepBusiness: "Business",
  stepIndustry: "Industry",
  stepPlan: "Plan",
  stepAccount: "Account",
  asideTitle: "AI voice agents for service businesses & call centers",
  asideBody:
    "Your workspace unlocks after Stripe confirms the subscription — not on the success redirect.",
  businessName: "Business name",
  businessId: "Workspace ID",
  businessIdHint: "Used at sign-in. Lowercase, numbers, hyphens.",
  timezone: "Timezone",
  industry: "Industry",
  industryHint: "We’ll suggest the best starting template after checkout.",
  industries: [
    { key: "home_services", label: "Home & field services" },
    { key: "healthcare", label: "Healthcare & clinics" },
    { key: "legal_insurance", label: "Legal & insurance" },
    { key: "real_estate", label: "Real estate" },
    { key: "call_center", label: "Call center" },
    { key: "hospitality", label: "Restaurants & hospitality" },
    { key: "other", label: "Other service business" },
  ],
  yourName: "Your name",
  email: "Work email",
  password: "Password",
  passwordHint: "At least 8 characters",
  plan: "Choose a plan",
  back: "Back",
  continue: "Continue",
  submit: "Continue to checkout",
  submitting: "Starting checkout…",
  failedTitle: "Could not start signup",
  failedMessage: "Check your details and try again.",
  canceled: "Checkout was canceled. Pick a plan and try again when you’re ready.",
  signIn: "Already have an account? Sign in",
  comparePlans: "See plan details on the homepage",
} as const;

export const footer = {
  tagline: "AI Voice Platform for service businesses and call centers.",
  note: "Reception, support, sales, booking, and handoff — one multi-tenant platform.",
  columns: [
    {
      title: "Product",
      links: [
        { label: "Voice demo", href: "/#demo" },
        { label: "Features", href: "/#features" },
        { label: "Industries", href: "/#industries" },
        { label: "Pricing", href: "/#pricing" },
      ],
    },
    {
      title: "Get started",
      links: [
        { label: "Start free trial", href: "/signup" },
        { label: "Sign in", hrefEnv: "login" as const },
        { label: "Ops console", hrefEnv: "ops" as const },
      ],
    },
    {
      title: "Company",
      links: [
        { label: "FAQ", href: "/#faq" },
        { label: "Ops playground", hrefEnv: "playground" as const },
      ],
    },
  ],
} as const;
