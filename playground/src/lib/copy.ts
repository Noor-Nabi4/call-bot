/** Customer-facing copy for the public playground. Keep localization-ready. */

export const site = {
  title: "Call Bot — AI Receptionist for Service Businesses",
  description:
    "Answer customer calls, capture service requests, schedule appointments, and support your operations with an AI receptionist.",
  brand: "Call Bot",
  navVoice: "Voice",
  navPhone: "Phone setup",
} as const;

export const home = {
  heading: "Answer every call with a reliable AI receptionist.",
  supporting:
    "Handle customer calls, capture service requests, schedule appointments, and keep your team informed—even when no one is available to answer.",
  primaryAction: "Try the voice assistant",
  secondaryAction: "Set up a phone number",
  trust:
    "Built for service businesses that need faster response times and fewer missed opportunities.",
  privacy:
    "Your business data is available only to authorized users in your organization.",
} as const;

export const voice = {
  sessionLabel: "Call status",
  ready: "Ready to start",
  connecting: "Connecting",
  listening: "Listening",
  preparing: "Preparing a response",
  speaking: "Speaking",
  interrupted: "Listening",
  ended: "Call ended",
  connectionProblem: "Connection problem",
  waitingHint:
    "Waiting for the assistant to speak. Allow microphone access when prompted.",
  idleHint:
    "Start a call to hear how the AI receptionist greets customers and takes requests.",
  startCall: "Start call",
  endCall: "End call",
  connectingAction: "Connecting…",
  startFailed: "We could not start the call. Please try again.",
  interruptedError:
    "The connection was interrupted. Start a new call to continue.",
} as const;

export const telephony = {
  heading: "Set up a phone number",
  supporting:
    "Connect the number customers already know, or get a new business number for your AI receptionist.",
  steps: [
    { id: "number", label: "Choose a number option" },
    { id: "provider", label: "Connect your provider" },
    { id: "configure", label: "Configure call routing" },
    { id: "test", label: "Test an incoming call" },
    { id: "activate", label: "Activate the number" },
  ] as const,
  existingTitle: "Connect your existing business number",
  existingBody:
    "Keep the phone number your customers already know and route incoming calls to your AI receptionist.",
  newTitle: "Get a new business number",
  newBody:
    "Search available numbers, choose one for your business, and connect it to your AI receptionist.",
  continue: "Continue",
  back: "Back",
  providerHeading: "Connect your provider",
  providerBody:
    "Connect your phone provider account so calls can reach your AI receptionist.",
  businessName: "Business name",
  businessSlug: "Business ID",
  createBusiness: "Create business",
  phoneNumber: "Business phone number",
  phonePlaceholder: "+15551234567",
  connectNumber: "Connect number",
  providerConnectionId: "Provider connection ID",
  providerConnectionHint: "Optional. Used only for your organization’s setup.",
  confirmRouting: "Confirm call routing",
  setupReady:
    "Connection details are ready. Confirm call routing, then test an incoming call.",
  searchNumbers: "Search",
  country: "Country",
  areaCode: "Area code",
  confirmPurchase: "Confirm purchase",
  searchEmpty: "Search to see available numbers for your business.",
  testHeading: "Test an incoming call",
  testBody:
    "Place a test call to confirm callers reach your AI receptionist. Follow the on-screen instructions from your provider.",
  startTest: "Start test call",
  activateHeading: "Activate the number",
  activateBody:
    "Your number activates after a successful test call. Refresh to check the latest status.",
  refresh: "Refresh status",
  noNumbers: "No numbers connected yet.",
  activity: "Activity",
  noActivity: "No activity yet.",
  statusConnection: "Connection",
  statusVerification: "Verification",
  advancedConnection: "Advanced connection settings",
  serviceUrl: "Service URL",
  genericError: "Something went wrong. Please try again.",
} as const;
