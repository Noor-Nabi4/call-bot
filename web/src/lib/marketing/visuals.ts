/** Visual system config for marketing product mockups and media. */

export type FlowStep = {
  label: string;
  detail?: string;
  tone?: "default" | "accent" | "muted" | "success";
};

export type BranchStep = {
  label: string;
};

export const heroCallFlow = {
  title: "Live call · AI voice agent",
  status: "00:42",
  intent: "Book appointment · Service request",
  steps: [
    { label: "Incoming call", detail: "Main business line", tone: "default" },
    { label: "AI voice agent", detail: "Understands intent", tone: "accent" },
    { label: "Knowledge / CRM", detail: "Grounded answers", tone: "default" },
    { label: "Book · Qualify · Support", detail: "Action completed", tone: "success" },
    { label: "Human handoff", detail: "Context attached", tone: "muted" },
  ] satisfies FlowStep[],
  chips: ["Knowledge", "Booking", "Handoff"],
} as const;

export const receptionistFlow = {
  title: "AI receptionist workflow",
  alt: "Diagram of an AI receptionist answering a call, identifying intent, booking or qualifying, updating CRM, and transferring to a human",
  steps: [
    { label: "Incoming call", detail: "Business line rings" },
    { label: "AI receptionist", detail: "Greets in brand voice", tone: "accent" },
    { label: "Identify intent", detail: "Book, FAQ, or escalate" },
    { label: "Answer / Book / Qualify", detail: "Completes the task", tone: "success" },
    { label: "CRM updated", detail: "Notes + contact saved" },
    { label: "Human transfer", detail: "When a person is needed", tone: "muted" },
  ] satisfies FlowStep[],
} as const;

export const voiceAgentFlow = {
  title: "AI voice agent platform",
  alt: "Diagram of a caller reaching an AI voice agent that understands intent, searches knowledge, applies rules, updates CRM, books appointments, and transfers to a human",
  steps: [
    { label: "Caller", detail: "Inbound opportunity" },
    { label: "AI voice agent", detail: "Conversational intake", tone: "accent" },
  ] satisfies FlowStep[],
  branches: [
    { label: "Understands caller" },
    { label: "Searches knowledge" },
    { label: "Uses business rules" },
    { label: "Updates CRM" },
    { label: "Books appointment" },
    { label: "Transfers to human" },
  ] satisfies BranchStep[],
} as const;

export const industryVisuals: Record<
  string,
  {
    scenario: string;
    metric: string;
    metricLabel: string;
    steps: FlowStep[];
    accent: string;
    alt: string;
  }
> = {
  hvac: {
    scenario: "No-cool emergency",
    metric: "Same-day",
    metricLabel: "Dispatch window",
    accent: "Climate control",
    alt: "AI receptionist workflow for HVAC emergency service calls and appointment booking",
    steps: [
      { label: "Service call", detail: "No AC · July peak" },
      { label: "AI receptionist", detail: "Captures address + urgency", tone: "accent" },
      { label: "Qualify job", detail: "System type · access notes" },
      { label: "Book tech", detail: "Next available slot", tone: "success" },
      { label: "On-call handoff", detail: "If truly urgent", tone: "muted" },
    ],
  },
  plumbing: {
    scenario: "Active leak intake",
    metric: "Priority",
    metricLabel: "Routing",
    accent: "Plumbing & drain",
    alt: "AI receptionist workflow for plumbing leak calls and service booking",
    steps: [
      { label: "Leak call", detail: "Water at ceiling" },
      { label: "AI receptionist", detail: "Triage severity", tone: "accent" },
      { label: "Service area check", detail: "Coverage confirmed" },
      { label: "Book truck", detail: "Emergency window", tone: "success" },
      { label: "Dispatcher alert", detail: "Summary attached", tone: "muted" },
    ],
  },
  roofing: {
    scenario: "Storm inspection lead",
    metric: "Hot lead",
    metricLabel: "Sales queue",
    accent: "Roofing & exterior",
    alt: "AI receptionist workflow for roofing storm damage leads and inspection booking",
    steps: [
      { label: "Storm inquiry", detail: "Hail damage reported" },
      { label: "AI receptionist", detail: "Qualifies insurance job", tone: "accent" },
      { label: "Capture details", detail: "Address · timeline" },
      { label: "Book inspection", detail: "Estimator slot", tone: "success" },
      { label: "Sales follow-up", detail: "Notes in CRM", tone: "muted" },
    ],
  },
  electricians: {
    scenario: "EV charger install",
    metric: "Qualified",
    metricLabel: "Estimate ready",
    accent: "Electrical",
    alt: "AI receptionist workflow for electrician service calls and install lead qualification",
    steps: [
      { label: "Install inquiry", detail: "EV charger request" },
      { label: "AI receptionist", detail: "Collects panel details", tone: "accent" },
      { label: "Safety screen", detail: "Escalate if urgent" },
      { label: "Book consult", detail: "Site visit offered", tone: "success" },
      { label: "Estimator handoff", detail: "Context ready", tone: "muted" },
    ],
  },
  healthcare: {
    scenario: "New patient scheduling",
    metric: "Booked",
    metricLabel: "Front desk",
    accent: "Clinic ops",
    alt: "AI receptionist workflow for healthcare clinic appointment scheduling and FAQ answering",
    steps: [
      { label: "Patient call", detail: "First available visit" },
      { label: "AI receptionist", detail: "Non-clinical intake", tone: "accent" },
      { label: "Answer FAQs", detail: "Hours · location" },
      { label: "Book visit", detail: "Rules-based slots", tone: "success" },
      { label: "Staff escalation", detail: "Urgent symptoms", tone: "muted" },
    ],
  },
  dental: {
    scenario: "Hygiene rebooking",
    metric: "Filled",
    metricLabel: "Chair time",
    accent: "Dental practice",
    alt: "AI receptionist workflow for dental appointment booking and front-desk call coverage",
    steps: [
      { label: "Patient call", detail: "Cleaning request" },
      { label: "AI receptionist", detail: "Offers open times", tone: "accent" },
      { label: "Confirm details", detail: "Name · preference" },
      { label: "Book cleaning", detail: "Calendar updated", tone: "success" },
      { label: "Front desk", detail: "Complex cases only", tone: "muted" },
    ],
  },
  legal: {
    scenario: "New matter intake",
    metric: "Screened",
    metricLabel: "Consult ready",
    accent: "Law firm",
    alt: "AI receptionist workflow for law firm intake qualification and consult booking",
    steps: [
      { label: "Prospective client", detail: "New matter call" },
      { label: "AI receptionist", detail: "Runs intake questions", tone: "accent" },
      { label: "Fit filter", detail: "Practice area match" },
      { label: "Book consult", detail: "Attorney calendar", tone: "success" },
      { label: "Paralegal route", detail: "Existing clients", tone: "muted" },
    ],
  },
  "real-estate": {
    scenario: "Listing inquiry",
    metric: "Showing",
    metricLabel: "Booked",
    accent: "Real estate",
    alt: "AI receptionist workflow for real estate lead qualification and showing booking",
    steps: [
      { label: "Buyer call", detail: "Listing question" },
      { label: "AI receptionist", detail: "Approved listing FAQs", tone: "accent" },
      { label: "Qualify interest", detail: "Timeline · financing" },
      { label: "Book showing", detail: "Open window offered", tone: "success" },
      { label: "Agent alert", detail: "Hot lead summary", tone: "muted" },
    ],
  },
  restaurants: {
    scenario: "Reservation request",
    metric: "Seated",
    metricLabel: "Table held",
    accent: "Hospitality",
    alt: "AI receptionist workflow for restaurant reservation and hours questions",
    steps: [
      { label: "Guest call", detail: "Friday night rush" },
      { label: "AI receptionist", detail: "Hours · party size", tone: "accent" },
      { label: "Answer FAQs", detail: "Parking · policy" },
      { label: "Book table", detail: "Reservation saved", tone: "success" },
      { label: "Manager route", detail: "Events · complaints", tone: "muted" },
    ],
  },
  insurance: {
    scenario: "Quote request",
    metric: "Lead",
    metricLabel: "Producer queue",
    accent: "Agency",
    alt: "AI receptionist workflow for insurance quote intake and service routing",
    steps: [
      { label: "Shopper call", detail: "Auto quote" },
      { label: "AI receptionist", detail: "Collects quote fields", tone: "accent" },
      { label: "Service triage", detail: "COI vs claim vs quote" },
      { label: "Route to producer", detail: "Licensed human", tone: "success" },
      { label: "Claims escalate", detail: "Never invents advice", tone: "muted" },
    ],
  },
  "home-services": {
    scenario: "Same-day job request",
    metric: "Booked",
    metricLabel: "Field team",
    accent: "Field services",
    alt: "AI receptionist workflow for home service job intake and appointment booking",
    steps: [
      { label: "Homeowner call", detail: "Needs help today" },
      { label: "AI receptionist", detail: "Captures job type", tone: "accent" },
      { label: "Qualify + area", detail: "Urgency · location" },
      { label: "Book job", detail: "Capacity-aware slot", tone: "success" },
      { label: "Dispatch notes", detail: "Ops board ready", tone: "muted" },
    ],
  },
  "call-centers": {
    scenario: "Multi-caller containment",
    metric: "Deflected",
    metricLabel: "Live queue",
    accent: "Contact center",
    alt: "AI voice agent workflow for call center FAQ containment and human handoff",
    steps: [
      { label: "Multiple callers", detail: "Queue pressure" },
      { label: "AI voice agent", detail: "Intent + FAQ", tone: "accent" },
      { label: "Knowledge answer", detail: "Approved content" },
      { label: "Contain or route", detail: "Only escalate needed", tone: "success" },
      { label: "Human agent", detail: "Summary attached", tone: "muted" },
    ],
  },
};

export const useCaseVisuals: Record<
  string,
  {
    title: string;
    alt: string;
    steps: FlowStep[];
    result: string;
  }
> = {
  "appointment-booking": {
    title: "Appointment booking flow",
    alt: "Workflow showing a phone call moving through an AI agent to a calendar and confirmed appointment",
    result: "Appointment confirmed",
    steps: [
      { label: "Phone call", detail: "Caller wants a time" },
      { label: "AI agent", detail: "Understands request", tone: "accent" },
      { label: "Service type", detail: "Visit reason captured" },
      { label: "Availability", detail: "Next available: 10:30 AM" },
      { label: "Confirmed", detail: "Calendar updated", tone: "success" },
    ],
  },
  "lead-qualification": {
    title: "Lead qualification flow",
    alt: "Workflow showing a caller qualified by an AI agent into CRM for the sales team",
    result: "Lead qualified",
    steps: [
      { label: "Lead", detail: "Inbound interest" },
      { label: "AI questions", detail: "Budget · timeline · need", tone: "accent" },
      { label: "Qualification", detail: "Fit scored by rules" },
      { label: "CRM updated", detail: "Structured notes saved", tone: "success" },
      { label: "Sales team", detail: "Rep notified", tone: "muted" },
    ],
  },
  "customer-support": {
    title: "Customer support flow",
    alt: "Workflow showing a support call answered from a knowledge base with optional human escalation",
    result: "Answered or handed off",
    steps: [
      { label: "Caller", detail: "Support question" },
      { label: "AI agent", detail: "Customer verified", tone: "accent" },
      { label: "Knowledge", detail: "Approved answers" },
      { label: "Answer", detail: "Issue resolved", tone: "success" },
      { label: "Human handoff", detail: "Context preserved", tone: "muted" },
    ],
  },
  "call-answering": {
    title: "Call answering flow",
    alt: "Workflow showing an incoming call answered by an AI receptionist and routed to the right next step",
    result: "Answered + routed",
    steps: [
      { label: "Incoming call", detail: "Never to voicemail" },
      { label: "AI receptionist", detail: "Brand greeting", tone: "accent" },
      { label: "Intent", detail: "Book · FAQ · transfer" },
      { label: "Answer / route / book", detail: "Right next step", tone: "success" },
    ],
  },
  "sales-calls": {
    title: "Inbound sales flow",
    alt: "Workflow showing an inbound sales lead handled by an AI agent, written to CRM, and handed to a sales rep",
    result: "Transferred to Sales",
    steps: [
      { label: "Lead", detail: "High-intent call" },
      { label: "AI agent", detail: "Qualifies + captures", tone: "accent" },
      { label: "Qualify", detail: "ICP rules applied" },
      { label: "CRM updated", detail: "Opportunity created", tone: "success" },
      { label: "Sales rep", detail: "Closer ready", tone: "muted" },
    ],
  },
};

export const blogCovers: Record<
  string,
  {
    src?: string;
    theme: "waveform" | "receptionist" | "platform";
    alt: string;
  }
> = {
  "what-is-an-ai-receptionist": {
    theme: "receptionist",
    alt: "Abstract product visual representing an AI receptionist answering a business phone call",
  },
  "ai-voice-agents-vs-chatbots": {
    src: "/images/hero/ai-voice-ops.jpg",
    theme: "waveform",
    alt: "Laptop displaying a teal voice waveform beside a business phone and headset in a modern office",
  },
};

export const mediaAssets = {
  voiceOps: {
    src: "/images/hero/ai-voice-ops.jpg",
    width: 1600,
    height: 1066,
    alt: "AI voice operations desk with a teal waveform on a laptop, headset, and business phone",
  },
  platformOps: {
    src: "/images/product/voice-ops-dashboard.jpg",
    width: 1600,
    height: 1066,
    alt: "Operations console with dual monitors showing voice analytics and CRM dashboards",
  },
  bookingDesk: {
    src: "/images/use-cases/appointment-calendar.jpg",
    width: 1600,
    height: 1066,
    alt: "Workspace with a digital calendar on a laptop for appointment scheduling",
  },
  industryHub: {
    src: "/images/industries/industry-hub.jpg",
    width: 1600,
    height: 1066,
    alt: "Professional operations workspace representing industry-ready AI phone workflows",
  },
} as const;

export const pricingVisual = {
  title: "Usage that scales with calls",
  alt: "Illustration of AI voice minutes, concurrent calls, and phone numbers across pricing plans",
  meters: [
    { label: "Voice minutes", value: 72 },
    { label: "Concurrent calls", value: 45 },
    { label: "Phone numbers", value: 38 },
  ],
} as const;
