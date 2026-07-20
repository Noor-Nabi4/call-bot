/** Customer-facing copy for the operations console. Keep localization-ready. */

export const site = {
  title: "Call Bot — Operations",
  description:
    "Manage calls, appointments, and field jobs for your service business.",
  brand: "Call Bot",
  product: "Operations",
  tagline: "Operations",
} as const;

export const login = {
  brand: "Call Bot",
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
  new: "New",
  scheduled: "Scheduled",
  dispatched: "Dispatched",
  in_progress: "In progress",
  completed: "Completed",
  canceled: "Canceled",
  cancelled: "Canceled",
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
    "Manage data retention, review account activity, and open billing or team.",
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
  deactivated: "Teammate deactivated",
  reactivated: "Teammate reactivated",
  noUsers: "No team members yet",
  noUsersHint: "Invite teammates to access your organization.",
} as const;

export const billing = {
  title: "Billing",
  description:
    "Subscription status comes from Stripe webhooks. Completing Checkout does not activate your plan until Stripe confirms it.",
  confirming: "Confirming with Stripe…",
  confirmingHint:
    "Payment succeeded in Checkout. Waiting for Stripe to confirm your subscription.",
  noSubscription: "No subscription on file",
  noSubscriptionHint:
    "Complete Checkout to start a plan. Status updates only after Stripe webhooks arrive.",
  plan: "Plan",
  status: "Status",
  periodEnd: "Current period ends",
  cancelAtPeriodEnd: "Cancels at period end",
  entitlements: "Plan limits",
  minutes: "Included voice minutes",
  minutesUsed: "Voice minutes this month",
  usage: "Usage this month",
  usageHint:
    "Minutes are counted from call start to end (UTC calendar month). Overage is estimated from your plan rate.",
  overage: "Estimated overage",
  calls: "Ended calls",
  resources: "Resource usage",
  concurrent: "Concurrent calls",
  numbers: "Phone numbers",
  users: "Team users",
  knowledge: "Knowledge documents",
  dispatch: "Dispatch board",
  techMobile: "Technician mobile",
  manage: "Manage billing",
  managing: "Opening portal…",
  completeCheckout: "Complete checkout",
  startingCheckout: "Starting checkout…",
  active: "Your subscription is active.",
  loadFailed: "Could not load billing details.",
  portalFailed: "Could not open the billing portal.",
  checkoutFailed: "Could not start checkout.",
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
  emptyHint: "Customers appear when calls and jobs are created.",
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
  createAction: "Create rule",
  saving: "Saving…",
  created: "Automation created",
  enabled: "Automation enabled",
  disabled: "Automation disabled",
  deleted: "Automation deleted",
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
