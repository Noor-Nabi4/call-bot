/** Site copy for the CallBot marketing landing. */

export const site = {
  brand: "CallBot",
  title: "CallBot | AI Voice Platform for Growing Businesses",
  description:
    "CallBot is an AI voice platform for businesses and call centers. Deploy AI receptionists, support agents, and sales agents that book appointments, answer from your knowledge base, and hand off to humans.",
} as const;

export const hero = {
  brand: "CallBot",
  eyebrow: "AI Voice Platform",
  headline: "Answer Every Call With AI",
  supporting:
    "Deploy intelligent AI voice agents for customer support, appointment booking, sales, and call centers using one scalable platform.",
  primaryCta: "Start Free Trial",
  secondaryCta: "Book Demo",
  trustItems: [
    "AI receptionist & support",
    "Appointment booking",
    "Human handoff included",
  ],
} as const;

export const trustedBy = {
  title: "Trusted across industries that live on the phone",
  logos: [
    "Healthcare",
    "Legal",
    "Insurance",
    "Real Estate",
    "Restaurants",
    "Home Services",
    "Call Centers",
    "Field Service",
  ],
} as const;

export const whyChoose = {
  title: "Why teams choose CallBot",
  supporting:
    "One platform to greet callers, resolve requests, book work, and escalate — without stitching together separate tools.",
  items: [
    {
      title: "Never miss a call",
      body: "AI agents answer around the clock in your brand voice, so after-hours and overflow calls still convert.",
    },
    {
      title: "Book while you talk",
      body: "Capture details and offer real appointment windows during the conversation — no voicemail callback loop.",
    },
    {
      title: "Escalate with context",
      body: "When a caller needs a person, your team picks up with a clear summary of what already happened.",
    },
    {
      title: "Scale without chaos",
      body: "Multi-tenant workspaces keep each business’s numbers, knowledge, and agents cleanly separated.",
    },
  ],
} as const;

export const platform = {
  title: "Every capability maps to real phone work",
  supporting:
    "Reception, support, sales, booking, and handoff — designed so operators stay in control from the first ring.",
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
      body: "Resolve FAQs from approved documents, open follow-ups when needed, and escalate billing or account issues cleanly.",
      previewLabel: "Support agent",
      previewLines: [
        "Knowledge match found",
        "Answer confirmed",
        "Ticket created",
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
        "Thursday 10:30 AM",
        "Appointment confirmed",
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

export const features = {
  title: "Voice agent capabilities that matter",
  supporting:
    "Built for real phone conversations — not chatbot scripts read aloud.",
  items: [
    {
      title: "Natural conversations",
      body: "Callers hear a clear, professional voice that listens, clarifies, and keeps the call moving.",
    },
    {
      title: "Appointment booking",
      body: "Offer available slots, confirm details, and write bookings your team can trust.",
    },
    {
      title: "Knowledge base answers",
      body: "Ground replies in your approved documents so answers stay accurate and on-brand.",
    },
    {
      title: "Human handoff",
      body: "Transfer to a teammate or capture a callback when the situation needs a person.",
    },
    {
      title: "Multi-tenant control",
      body: "Run many businesses or brands from one platform with isolated settings and data.",
    },
    {
      title: "Ops visibility",
      body: "Monitor live calls, review outcomes, and improve scripts from a shared operations console.",
    },
  ],
} as const;

export const industries = {
  title: "Ready for your industry",
  supporting:
    "Configure agents for the way your callers talk — then keep your own numbers, knowledge, and branding.",
  items: [
    {
      name: "Healthcare",
      body: "Front-desk coverage for scheduling, hours, and routing — without inventing clinical advice.",
    },
    {
      name: "Legal & insurance",
      body: "Intake new matters, gather case basics, and route urgent calls to the right desk.",
    },
    {
      name: "Real estate & home services",
      body: "Qualify inquiries, book estimates, and capture address and job details on the first call.",
    },
    {
      name: "Restaurants & hospitality",
      body: "Handle reservations, hours, and location questions when your team is mid-service.",
    },
    {
      name: "Call centers",
      body: "Automate high-volume FAQs and overflow while supervisors keep full visibility.",
    },
    {
      name: "Small & mid-size businesses",
      body: "Sound bigger than your headcount with always-on phone coverage that books work.",
    },
  ],
} as const;

export const howItWorks = {
  title: "How CallBot works",
  supporting:
    "Go from signup to live answering without a lengthy implementation project.",
  steps: [
    {
      title: "Easy setup",
      body: "Create your workspace, invite your team, and get your first agent ready in minutes.",
      previewLabel: "Workspace",
      previewLines: [
        "Business profile created",
        "Team seats invited",
        "Agent draft ready",
      ],
    },
    {
      title: "Configure",
      body: "Set greeting, knowledge, booking rules, and handoff preferences for reception, support, or sales.",
      previewLabel: "Agent",
      previewLines: [
        "Knowledge connected",
        "Booking windows set",
        "Handoff rules active",
      ],
    },
    {
      title: "Go live",
      body: "Connect a business number, answer real callers, and improve from live call outcomes.",
      previewLabel: "Live calls",
      previewLines: [
        "Number routed",
        "Inbound call answered",
        "Booking confirmed",
      ],
    },
  ],
} as const;

export const integrations = {
  title: "Fits the tools you already use",
  supporting:
    "Connect calendars, CRMs, and notification channels so bookings and handoffs land where work already happens.",
  items: [
    {
      title: "Calendars & scheduling",
      body: "Sync availability so agents offer slots your team can actually honor.",
    },
    {
      title: "CRM & customer records",
      body: "Look up known callers and write new leads without retyping from voicemail.",
    },
    {
      title: "Team alerts",
      body: "Notify the right people when a handoff, booking, or urgent request lands.",
    },
    {
      title: "Webhooks & API",
      body: "Push call events into your own systems with signed webhooks and tenant API keys.",
    },
  ],
} as const;

export const analytics = {
  title: "See what every call accomplished",
  supporting:
    "Operators need more than a recording — they need outcomes they can act on.",
  metrics: [
    {
      label: "Answer rate",
      body: "Track how many inbound calls your agents pick up versus miss.",
    },
    {
      label: "Bookings created",
      body: "Measure appointments and follow-ups captured during conversations.",
    },
    {
      label: "Handoffs",
      body: "Understand when callers need a human and how quickly the team responds.",
    },
    {
      label: "Knowledge coverage",
      body: "Spot questions your docs do not answer yet and close the gaps.",
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

export const testimonials = {
  title: "What operators say",
  supporting: "Teams use CallBot to keep phones covered without adding headcount overnight.",
  items: [
    {
      quote:
        "We stopped losing after-hours jobs. Callers book estimates while we sleep, and the office opens with a full schedule.",
      name: "Operations lead",
      role: "Home services company",
    },
    {
      quote:
        "The handoff queue is the difference. When someone needs a person, my team already knows why they called.",
      name: "Support manager",
      role: "Regional call center",
    },
    {
      quote:
        "Multi-location clinics stay separate in CallBot, but we still manage everything from one place.",
      name: "Practice administrator",
      role: "Healthcare group",
    },
  ],
} as const;

export const faq = {
  title: "Frequently asked questions",
  supporting: "Straight answers about how CallBot helps your callers and your team.",
} as const;

export const close = {
  title: "Ready to answer every call?",
  body: "Start a free trial, configure your first voice agent, and put CallBot on a number your customers already dial.",
  primaryCta: "Start Free Trial",
  secondaryCta: "View pricing",
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
  tagline: "AI Voice Platform for businesses and call centers.",
  note: "Reception, support, sales, booking, and handoff — one multi-tenant platform.",
  columns: [
    {
      title: "Product",
      links: [
        { label: "Platform", href: "#platform" },
        { label: "Features", href: "#features" },
        { label: "Pricing", href: "/#pricing" },
        { label: "How it works", href: "#how-it-works" },
      ],
    },
    {
      title: "Solutions",
      links: [
        { label: "AI Receptionist", href: "#platform" },
        { label: "Call centers", href: "#industries" },
        { label: "Healthcare", href: "#industries" },
        { label: "Home services", href: "#industries" },
      ],
    },
    {
      title: "Company",
      links: [
        { label: "Sign up", href: "/signup" },
        { label: "Sign in", hrefEnv: "login" as const },
        { label: "Ops console", hrefEnv: "ops" as const },
        { label: "Voice demo", hrefEnv: "playground" as const },
      ],
    },
  ],
} as const;
