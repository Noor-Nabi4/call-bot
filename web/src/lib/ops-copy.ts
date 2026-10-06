/** Customer-facing copy for the operations console. Keep localization-ready. */

export const site = {
  title: "Call & Flow — Operations",
  description:
    "Manage calls, appointments, and field jobs for your service business.",
  brand: "Call & Flow",
  product: "Operations",
  tagline: "Operations",
} as const;

export const login = {
  brand: "Call & Flow",
  heading: "Sign in",
  supporting: "Access your business dashboard and field operations.",
  businessId: "Business ID",
  email: "Email",
  password: "Password",
  submit: "Sign in",
  submitting: "Signing in…",
  failedTitle: "Sign-in failed",
  failedMessage: "Check your business ID and credentials, then try again.",
} as const;

export const dashboard = {
  attentionLead: "Here is what needs your attention today.",
  activeJobs: "Active jobs",
  appointmentsToday: "Appointments today",
  availableTechnicians: "Available technicians",
  callsToday: "Calls today",
  needsAttention: "Needs attention",
  todaysSchedule: "Today’s schedule",
  recentActivity: "Recent activity",
  viewAll: "View all",
  noWorkToday: "No work scheduled for today",
  noWorkHint: "New jobs and appointments will appear here.",
} as const;

export const dispatch = {
  title: "Dispatch",
  description: "Assign technicians and move jobs through the service workflow.",
  createJob: "Create job",
  addTechnician: "Add technician",
  unassigned: "Unassigned",
  scheduled: "Scheduled",
  dispatched: "Dispatched",
  inProgress: "In progress",
  completed: "Completed",
  overdue: "Overdue",
  emptyStage: "No jobs in this stage",
  noMatch: "No jobs match filters",
  noMatchHint: "Clear filters or create a job to get started.",
} as const;

export const jobStatusLabels: Record<string, string> = {
  NEW: "New",
  SCHEDULED: "Scheduled",
  CONFIRMED: "Confirmed",
  DISPATCHED: "Dispatched",
  EN_ROUTE: "En route",
  ARRIVED: "Arrived",
  IN_PROGRESS: "In progress",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
  NO_SHOW: "No show",
};

export const calls = {
  title: "Calls",
  description: "Review recent customer conversations and outcomes.",
  completed: "Completed",
  missed: "Missed",
  transferred: "Transferred",
  actionRequired: "Action required",
  appointmentBooked: "Appointment booked",
  empty: "No calls found for this period",
  emptyHint: "Call records appear when customers reach your AI receptionist.",
  detailTitle: "Call detail",
  liveLink: "Live now",
  quality: "Quality review",
  score: "Score (1–5)",
  disposition: "Disposition",
  notes: "Notes",
  saveQuality: "Save review",
  savingQuality: "Saving…",
  qualitySaved: "Quality review saved",
} as const;

export const liveCalls = {
  title: "Live calls",
  description:
    "Active conversations right now. Auto-refreshes; listen-in and barge come later.",
  empty: "No active calls",
  emptyHint: "When a caller connects, they will appear here within a few seconds.",
  elapsed: "Elapsed",
  handoff: "Handoff requested",
  history: "Call history",
  refreshing: "Refreshing…",
} as const;

export const supervisor = {
  title: "Supervisor",
  description:
    "Monitor live volume, handoffs, and recent outcomes. Listen-in and whisper are not available yet.",
  active: "Active now",
  handoffsOpen: "Open handoffs",
  callsToday: "Calls today",
  handoffsToday: "Handoffs today",
  avgDuration: "Avg duration today",
  attention: "Needs attention",
  attentionEmpty: "No open handoff requests",
  live: "Active calls",
  liveEmpty: "No active calls",
  recent: "Recent calls",
  recentEmpty: "No recent calls yet",
  openLive: "Open live view",
  openMetrics: "Metrics",
  refreshing: "Refreshing…",
} as const;

export const queue = {
  title: "Queue",
  description:
    "Handoff follow-ups waiting for a human. Skills-based routing and departments come later.",
  empty: "Queue is clear",
  emptyHint: "Items appear when a call ends after a handoff request.",
  claim: "Claim",
  complete: "Complete",
  cancel: "Cancel",
  cancelTitle: "Cancel queue item?",
  cancelBody:
    "This follow-up will be closed without completing the handoff work.",
  waiting: "Waiting",
  claimed: "Claimed",
  refreshing: "Refreshing…",
  filterAll: "Open",
  filterWaiting: "Waiting",
  filterClaimed: "Claimed",
} as const;

export const marketplace = {
  title: "Marketplace",
  description:
    "Install ready-made AI agents for your industry. Customize prompts and tools after install.",
  install: "Install",
  installing: "Installing…",
  installed: "Agent installed",
  installTitle: "Install this agent?",
  installBody:
    "{name} will create a new agent profile. You can customize prompts and tools after install.",
  featured: "Featured",
  all: "All categories",
  seedKnowledge: "Seed starter knowledge",
  setDefault: "Set as default agent",
  articles: "starter articles",
  empty: "No templates in this category",
  openAgent: "Open agent",
} as const;

export const apiKeys = {
  title: "API keys",
  description:
    "Issue keys for the public /v1 API (customers and calls read). Secrets are shown once.",
  create: "Create key",
  createHint: "The secret is shown once after creation. Store it securely.",
  creating: "Creating…",
  created: "API key created",
  name: "Name",
  scopesHint: "Scopes",
  empty: "No API keys yet",
  emptyHint: "Create a key to call GET /v1/customers and GET /v1/calls.",
  revoke: "Revoke",
  revokeTitle: "Revoke API key?",
  revokeBody:
    "{name} will stop working immediately. Existing integrations using this key will fail.",
  revoked: "API key revoked",
  active: "Active",
  inactive: "Revoked",
  secretOnce: "Copy this secret now — it will not be shown again.",
  dismissSecret: "I saved the secret",
} as const;

export const branding = {
  title: "Branding",
  description:
    "White-label Ops chrome: product name, logo, and brand colors. Custom domains come later.",
  productName: "Product name",
  logoUrl: "Logo URL",
  primaryColor: "Primary color",
  accentColor: "Accent / hover color",
  supportEmail: "Support email",
  save: "Save branding",
  saving: "Saving…",
  saved: "Branding saved",
  hint: "Applies to the Ops shell for your tenant",
} as const;

export const knowledge = {
  title: "Knowledge",
  description:
    "Manage the information your voice assistant can use when answering customers.",
  add: "Add article",
  edit: "Edit article",
  hideForm: "Hide form",
  save: "Save changes",
  saving: "Saving…",
  created: "Article created",
  updated: "Article updated",
  deleted: "Article deleted",
  deactivate: "Deactivate",
  reactivate: "Reactivate",
  deactivated: "Article deactivated",
  reactivated: "Article reactivated",
  processing: "Processing",
  ready: "Active",
  needsAttention: "Inactive",
  uploadFailed: "Upload failed",
  empty: "No documents uploaded yet",
  emptyHint: "Add articles so the assistant can answer common customer questions.",
  deleteTitle: "Delete article?",
  deleteBody:
    "This removes the article from your knowledge base. The assistant will no longer use it when answering customers.",
  agentScope: "Agent scope",
  agentScopeHint: "Shared articles apply to every agent. Profile-scoped ones only for that agent.",
  allAgents: "All agents (shared)",
  preview: "Search preview",
  previewHint:
    "Runs the same ranked search the voice assistant uses (active articles only).",
  previewPlaceholder: "Ask a customer question…",
  runPreview: "Preview",
  previewing: "Searching…",
  previewEmpty: "No active articles matched that query.",
  previewFailed: "Could not run knowledge preview.",
} as const;

export const settings = {
  title: "Settings",
  description:
    "Manage your business profile, data retention, billing, and team.",
  organization: "Business profile",
  organizationHint:
    "Legal and operating details for this tenant. Used for scheduling, invoices, and AI context.",
  organizationSaved: "Business profile saved",
  name: "Business name",
  industry: "Industry",
  businessType: "Business type",
  timezone: "Timezone",
  currency: "Currency",
  country: "Country",
  state: "State / region",
  website: "Website",
  phone: "Business phone",
  email: "Business email",
  users: "Team members",
  invite: "Invite teammate",
  retention: "Data retention",
  recordings: "Call recordings",
  transcripts: "Call transcripts",
  audit: "Activity log",
  noUsers: "No team members yet",
  noUsersHint: "Invite teammates to access your organization.",
  noAudit: "No activity yet",
  noAuditHint: "Administrative actions will appear here.",
  privacyData:
    "Your business data is available only to authorized users in your organization.",
  privacyRecordings:
    "Call recordings and transcripts are stored only when enabled by your organization.",
  privacyConfig:
    "Sensitive configuration values are never displayed publicly.",
  assistantLink: "Voice assistant",
  assistantLinkHint: "Edit how the phone assistant greets and helps callers.",
  billingLink: "Billing",
  billingLinkHint: "View your plan, usage, and manage payment in Stripe.",
  teamLink: "Team",
  teamLinkHint: "Invite teammates, change roles, and deactivate accounts.",
} as const;

export const team = {
  title: "Team",
  description:
    "Invite teammates within your plan seat limit. Deactivated users cannot sign in.",
  invite: "Invite teammate",
  inviteHint:
    "Share the temporary password securely. Teammates can change it after signing in.",
  inviteAction: "Invite",
  inviting: "Inviting…",
  invited: "Teammate invited",
  updated: "Teammate updated",
  deactivate: "Deactivate",
  reactivate: "Reactivate",
  deactivateTitle: "Deactivate teammate?",
  deactivateBody:
    "{name} will lose access immediately and cannot sign in until reactivated.",
  reactivateTitle: "Reactivate teammate?",
  reactivateBody: "{name} will be able to sign in again with their existing password.",
  deactivated: "Teammate deactivated",
  reactivated: "Teammate reactivated",
  noUsers: "No team members yet",
  noUsersHint: "Invite teammates to access your organization.",
  seatLimitReached:
    "Your plan seat limit is full. Upgrade billing or deactivate a user first.",
} as const;

export const billing = {
  title: "Billing",
  description: "Your plan, monthly usage, and payment settings.",
  confirming: "Confirming with Stripe…",
  confirmingHint:
    "Payment succeeded. Waiting a moment for your plan to activate.",
  noSubscription: "No plan yet",
  noSubscriptionHint:
    "Start checkout to choose a plan. Usage still appears below once calls begin.",
  plan: "Plan",
  status: "Status",
  periodEnd: "Renews",
  cancelAtPeriodEnd: "Cancels at period end",
  entitlements: "Included with your plan",
  minutes: "Voice minutes",
  minutesUsed: "Voice minutes",
  usage: "This month",
  usageHint: "UTC calendar month · overage estimated from your plan rate",
  overage: "Estimated overage",
  calls: "Calls",
  resources: "Capacity",
  concurrent: "Concurrent calls",
  numbers: "Phone numbers",
  users: "Team seats",
  knowledge: "Knowledge articles",
  dispatch: "Dispatch board",
  techMobile: "Technician app",
  manage: "Manage in Stripe",
  managing: "Opening…",
  completeCheckout: "Start checkout",
  startingCheckout: "Starting…",
  active: "Subscription active",
  loadFailed: "Could not load billing details.",
  portalFailed: "Could not open the billing portal.",
  checkoutFailed: "Could not start checkout.",
  featuresIncluded: "Included",
  featuresNotIncluded: "Not included",
} as const;

export const cogs = {
  title: "COGS & Profitability",
  description:
    "Monitor AI calling costs, revenue, margins, and vendor usage.",
  refresh: "Refresh",
  loadFailed: "Unable to load COGS data.",
  errorTitle: "Unable to load COGS data.",
  emptyTitle: "No COGS data available for this period.",
  emptyHint: "Calls with estimated costs will appear here after they end.",
  estimatedBanner: "All COGS figures are estimated internal costs",
  searchPlaceholder: "Search call ID",
  periodTotalsTitle: "Revenue vs COGS",
  periodTotalsHint: "Period totals from the summary API (not invented daily revenue).",
  revenueUnavailable:
    "Subscription revenue is only attributed to calendar months for this period.",
  dailyCogsTitle: "Daily variable COGS",
  dailyCogsHint:
    "From call_cogs. Daily revenue is not attributed — use period KPIs for revenue.",
  breakdownTitle: "COGS Breakdown",
  breakdownTableTitle: "Cost components",
  fixedTitle: "Fixed monthly costs",
  fixedHint: "Configured monthly estimate — not vendor invoices.",
  planTitle: "Plan Profitability",
  planHint:
    "Tenant plan only. Customer counts across the fleet are not available here.",
  channelTitle: "Usage & COGS by Channel",
  channelHint:
    "Browser/WebRTC excludes Twilio and LiveKit SIP. Revenue by channel is N/A.",
  callsTitle: "Call COGS",
  callsHint:
    "Estimated per-call vendor cost. Per-call revenue is not allocated.",
  detailHint: "Estimated internal cost detail",
} as const;

export const assistantSettings = {
  title: "Voice assistant",
  description:
    "Configure how your voice assistant sounds and what business facts it may share.",
  identity: "Identity",
  conversation: "Conversation",
  businessRules: "Business rules",
  escalation: "Escalation",
  advanced: "Advanced",
  businessName: "Business name",
  assistantName: "Assistant name",
  businessDescription: "Business description",
  greeting: "Greeting",
  greetingHint: "Guidance for the opening line — spoken naturally, not read verbatim.",
  tone: "Tone",
  responseStyle: "Response style",
  defaultLanguage: "Default language",
  supportedLanguages: "Supported languages",
  serviceAreas: "Service areas",
  businessHours: "Business hours summary",
  bookingRules: "Booking rules",
  pricingPolicy: "Pricing disclosure policy",
  handoffRules: "Handoff rules",
  restrictedTopics: "Restricted topics",
  customInstructions: "Custom instructions",
  customHint:
    "Configuration only. Cannot override safety, privacy, or tenant isolation rules.",
  profileVersion: "Profile version",
  lastUpdated: "Last updated",
  commaHint: "Comma-separated values",
  noPrompt:
    "System prompts and internal tooling are never shown here — only approved editable fields.",
  save: "Save assistant profile",
  saving: "Saving…",
  saved: "Assistant profile saved",
} as const;

export const handoff = {
  title: "Human transfer",
  description:
    "Decide when callers should be transferred to a live teammate.",
  enableTitle: "Enable human transfer",
  enableBody:
    "Allow the voice assistant to transfer callers to a live teammate when needed.",
  transferMode: "Transfer style",
  warm: "Assisted transfer",
  cold: "Direct transfer",
  escalationPhone: "Transfer phone number",
  escalationHint: "Number where live teammates answer escalated calls",
  connectionId: "Phone connection ID",
  connectionHint: "Required for assisted transfers. Keep this private.",
  connectionSummary: "Phone connection",
  save: "Save rules",
  saving: "Saving…",
  currentRules: "Current rules",
  whenTriggers: "When transfer happens",
  triggerNeedHuman: "The assistant detects the caller needs a person",
  triggerWarm: "An assisted transfer connects a teammate before releasing the caller",
  triggerCold: "A direct transfer sends the caller to your transfer number",
  triggerRoute: "Calls route to the configured transfer number",
  maskedUnset: "Not set",
} as const;

export const customers = {
  title: "Customers",
  description: "Customer records from calls, appointments, and jobs.",
  empty: "No customers yet",
  emptyHint: "Create a customer or wait for calls and jobs to add records.",
  create: "New customer",
  notFound: "Customer not found",
  timelineEmpty: "No timeline events yet",
  timelineEmptyHint: "Calls, jobs, appointments, and notes appear here.",
} as const;

export const products = {
  title: "Products",
  description: "Catalog items your team and voice assistant can reference.",
  empty: "No products yet",
  emptyHint: "Create a product to start building your catalog.",
  create: "New product",
  notFound: "Product not found",
  categoriesLink: "Manage categories",
} as const;

export const productCategories = {
  title: "Categories",
  description: "Organize products into a nested category tree.",
  empty: "No categories yet",
  emptyHint: "Create a root category, then nest children under it.",
  create: "New category",
  createChild: "Add child",
} as const;

export const appointments = {
  title: "Appointments",
  description: "Scheduled service visits for your customers.",
  empty: "No appointments",
  emptyHint: "Appointments appear when customers book a visit.",
} as const;

export const metrics = {
  title: "Metrics",
  description:
    "Call volume, voice minutes, handoffs, and job activity for your business.",
  empty: "No metrics available",
  emptyHint: "Metrics will appear once activity is recorded.",
  calls: "Calls",
  voiceMinutes: "Voice minutes",
  avgDuration: "Avg duration",
  handoffs: "Handoffs",
  avgQuality: "Avg QA score",
  appointments: "Appointments",
  jobs: "Jobs",
  callsByDay: "Call volume",
  callOutcomes: "Disconnect reasons",
  jobsByStatus: "Jobs by status",
  noCallVolume: "No calls in this window.",
  noDisconnect: "No ended calls in this window.",
} as const;

export const automations = {
  title: "Automations",
  description:
    "Run follow-up jobs or audit events when calls end, handoffs happen, or appointments are booked.",
  create: "New rule",
  createHint:
    "Pick a trigger and action. Rules run for events in your organization.",
  createAction: "Create rule",
  saving: "Saving…",
  created: "Automation created",
  enabled: "Automation enabled",
  disabled: "Automation disabled",
  deleted: "Automation deleted",
  deleteTitle: "Delete automation?",
  deleteBody: "{name} will stop running immediately and cannot be restored.",
  enable: "Enable",
  disable: "Disable",
  delete: "Delete",
  inactive: "paused",
  empty: "No automations yet",
  emptyHint: "Create a rule to react to handoffs or bookings automatically.",
} as const;

export const callFlow = {
  title: "Call flow",
  description:
    "Ordered steps the voice assistant should follow. Saved to this agent and compiled into call instructions.",
  hint: "This is a linear flow editor. Full branching graphs can layer on later without changing these steps.",
  backToAgent: "Back to agent",
  addStep: "Add step",
  save: "Save flow",
  saving: "Saving…",
  saved: "Call flow saved",
  empty: "No steps yet. Add a greeting to get started.",
  step: "Step",
  label: "Label",
  type: "Type",
  status: "Status",
  enabled: "Enabled",
  disabled: "Disabled",
  instruction: "Guidance",
} as const;

export const tech = {
  title: "My jobs",
  description: "Today’s assigned field work.",
  empty: "No active assigned jobs",
  emptyHint: "New assignments will appear here when dispatched.",
} as const;

export const profile = {
  title: "Your profile",
  description: "Update how your name appears and change your password.",
  name: "Display name",
  email: "Email",
  role: "Role",
  business: "Business",
  currentPassword: "Current password",
  newPassword: "New password",
  confirmPassword: "Confirm new password",
  save: "Save profile",
  saving: "Saving…",
  saved: "Profile updated",
  passwordMismatch: "New password and confirmation do not match.",
  passwordHint: "Leave blank to keep your current password.",
  emailReadonly: "Email cannot be changed here. Ask an admin if you need a new login.",
} as const;

export const notifications = {
  title: "Needs attention",
  empty: "You’re all caught up.",
  emptyHint: "Unassigned jobs, overdue work, and handoff issues show up here.",
  refresh: "Refresh",
  viewDispatch: "Open dispatch",
  loadFailed: "Could not load alerts.",
  summary: "Summary",
  jobs: "Jobs",
  liveIdle: "Live updates on",
} as const;

export const errors = {
  generic: "Something went wrong. Please try again.",
  loadFailed: "We could not load this page. Please try again.",
  saveFailed: "We could not save your changes. Please try again.",
  createFailed: "We could not create that item. Please try again.",
  deleteFailed: "We could not delete that item. Please try again.",
} as const;
