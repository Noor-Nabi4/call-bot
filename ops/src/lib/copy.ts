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
} as const;

export const knowledge = {
  title: "Knowledge",
  description:
    "Manage the information your voice assistant can use when answering customers.",
  add: "Add article",
  processing: "Processing",
  ready: "Ready",
  needsAttention: "Needs attention",
  uploadFailed: "Upload failed",
  empty: "No documents uploaded yet",
  emptyHint: "Add articles so the assistant can answer common customer questions.",
  deleteTitle: "Delete article?",
  deleteBody:
    "This removes the article from your knowledge base. The assistant will no longer use it when answering customers.",
} as const;

export const settings = {
  title: "Settings",
  description:
    "Invite teammates, manage data retention, and review account activity.",
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
  description: "Call, appointment, and job activity for your business.",
  empty: "No metrics available",
  emptyHint: "Metrics will appear once activity is recorded.",
} as const;

export const tech = {
  title: "My jobs",
  description: "Today’s assigned field work.",
  empty: "No active assigned jobs",
  emptyHint: "New assignments will appear here when dispatched.",
} as const;

export const errors = {
  generic: "Something went wrong. Please try again.",
  loadFailed: "We could not load this page. Please try again.",
  saveFailed: "We could not save your changes. Please try again.",
  createFailed: "We could not create that item. Please try again.",
  deleteFailed: "We could not delete that item. Please try again.",
} as const;
