/**
 * Human-centric campaign visual registry.
 * Story spine: REAL PERSON → CALL → AI VOICE AGENT → BUSINESS ACTION
 *
 * Keep this module free of `@/` value imports so node-based seo tests can load it.
 */

export type BusinessOverlayKind =
  | "incoming-call"
  | "ai-agent"
  | "outcome"
  | "status";

export type BusinessOverlayPosition =
  | "top-left"
  | "top-center"
  | "top-right"
  | "center"
  | "bottom-left"
  | "bottom-right"
  | "right";

export type BusinessOverlayCard = {
  id: string;
  kind: BusinessOverlayKind;
  title: string;
  subtitle?: string;
  detail?: string;
  meta?: string;
  position: BusinessOverlayPosition;
};

export type HumanBusinessVisualConfig = {
  slug: string;
  category: "industry" | "use-case";
  image: {
    src: string;
    alt: string;
    width: number;
    height: number;
  };
  personRole: string;
  environment: string;
  workflow: readonly string[];
  /** Optional supporting 3D asset from the existing library. */
  threeDAsset?: {
    src: string;
    alt: string;
    width: number;
    height: number;
  };
  overlayCards: readonly BusinessOverlayCard[];
  /**
   * Campaign photographs already include glass UI storytelling.
   * When true, HTML overlays stay off unless explicitly forced.
   */
  bakedOverlays: boolean;
  focus: string;
  variant: "hero" | "spotlight" | "compact";
};

const SIZE = { width: 1280, height: 720 } as const;

function img(src: string, alt: string) {
  return { src, alt, ...SIZE };
}

function threeD(src: string, alt: string) {
  return { src, alt, ...SIZE };
}

function industryConfig(
  slug: string,
  config: Omit<HumanBusinessVisualConfig, "slug" | "category">,
): HumanBusinessVisualConfig {
  return { slug, category: "industry", ...config };
}

function buildUseCaseConfig(
  slug: string,
  config: Omit<HumanBusinessVisualConfig, "slug" | "category">,
): HumanBusinessVisualConfig {
  return { slug, category: "use-case", ...config };
}

export const industryBusinessVisuals: Record<string, HumanBusinessVisualConfig> =
  {
    hvac: industryConfig("hvac", {
      image: img(
        "/images/human/business/industries/hvac.jpg",
        "HVAC dispatcher handling an inbound service call with AI receptionist and technician scheduling",
      ),
      personRole: "HVAC dispatcher",
      environment: "Modern HVAC service office",
      workflow: [
        "Incoming Call",
        "AI Receptionist",
        "Service Request",
        "Technician Scheduled",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/hvac.jpg",
        "Illustration of HVAC service equipment with an incoming call and scheduling card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Incoming Call",
          subtitle: "Service request",
          detail: "No cool · Main line",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Receptionist",
          subtitle: "How can I help you today?",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Technician Scheduled",
          subtitle: "Service appointment",
          detail: "Thu · 10:30 AM window",
          meta: "Dispatch confirmed",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[28%_22%]",
      variant: "hero",
    }),
    plumbing: industryConfig("plumbing", {
      image: img(
        "/images/human/business/industries/plumbing.jpg",
        "Plumbing company dispatcher on a customer service call with AI triage and plumber dispatch",
      ),
      personRole: "Plumbing dispatcher",
      environment: "Plumbing business office",
      workflow: [
        "Emergency Call",
        "AI Understands Request",
        "Service Slot",
        "Plumber Dispatched",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/plumbing.jpg",
        "Illustration of a plumbing emergency call with dispatch scheduling context",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Emergency Call",
          subtitle: "Active leak",
          detail: "Priority triage",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Receptionist",
          subtitle: "Capturing service details",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Plumber Dispatched",
          subtitle: "Service slot reserved",
          detail: "Next available window",
          meta: "Truck assigned",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[30%_20%]",
      variant: "hero",
    }),
    roofing: industryConfig("roofing", {
      image: img(
        "/images/human/business/industries/roofing.jpg",
        "Roofing office professional receiving a homeowner inquiry with AI lead qualification",
      ),
      personRole: "Roofing office lead",
      environment: "Roofing company project office",
      workflow: [
        "Homeowner Call",
        "AI Qualifies Lead",
        "Estimate Request",
        "Sales Rep Follow-up",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/roofing.jpg",
        "Illustration of a roofing estimate request with an inbound call and lead card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Homeowner Call",
          subtitle: "Estimate inquiry",
          detail: "Storm inspection",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Qualifier",
          subtitle: "Collecting project details",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Lead Qualified",
          subtitle: "Estimate requested",
          detail: "Ready for sales follow-up",
          meta: "Rep notified",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[32%_18%]",
      variant: "hero",
    }),
    electricians: industryConfig("electricians", {
      image: img(
        "/images/human/business/industries/electricians.jpg",
        "Electrical service dispatcher answering a customer call with AI issue capture and technician assignment",
      ),
      personRole: "Electrical dispatcher",
      environment: "Electrical service office",
      workflow: [
        "Customer Call",
        "AI Captures Issue",
        "Service Appointment",
        "Electrician Assigned",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/electricians.jpg",
        "Illustration of an electrical service request with call and appointment booking",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Customer Call",
          subtitle: "Service issue",
          detail: "Panel / outlet request",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Receptionist",
          subtitle: "Capturing the issue",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Electrician Assigned",
          subtitle: "Appointment booked",
          detail: "Service window locked",
          meta: "Tech notified",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[28%_22%]",
      variant: "hero",
    }),
    healthcare: industryConfig("healthcare", {
      image: img(
        "/images/human/business/industries/healthcare.jpg",
        "Clinic receptionist handling a patient call with AI receptionist and appointment coordination",
      ),
      personRole: "Clinic receptionist",
      environment: "Modern medical clinic reception",
      workflow: [
        "Patient Call",
        "AI Receptionist",
        "Appointment",
        "Clinic Staff",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/healthcare.jpg",
        "Illustration of a healthcare clinic booking workflow with a call and calendar card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Patient Call",
          subtitle: "Scheduling request",
          detail: "Main clinic line",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Receptionist",
          subtitle: "How can I help you today?",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Appointment Ready",
          subtitle: "Clinic calendar",
          detail: "Slot held for staff confirm",
          meta: "Patient notified",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[30%_20%]",
      variant: "hero",
    }),
    dental: industryConfig("dental", {
      image: img(
        "/images/human/business/industries/dental.jpg",
        "Dental receptionist answering a patient call with AI receptionist and appointment confirmation",
      ),
      personRole: "Dental receptionist",
      environment: "Modern dental clinic reception",
      workflow: [
        "Incoming Call",
        "AI Receptionist",
        "Appointment Available",
        "Appointment Confirmed",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/dental.jpg",
        "Illustration of a dental appointment booking workflow with a call and calendar card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Incoming Call",
          subtitle: "Patient line",
          detail: "Scheduling request",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Receptionist",
          subtitle: "How can I help you today?",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Appointment Confirmed",
          subtitle: "Calendar updated",
          detail: "Thu · 10:30 AM",
          meta: "Confirmation sent",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[26%_24%]",
      variant: "hero",
    }),
    legal: industryConfig("legal", {
      image: img(
        "/images/human/business/industries/legal.jpg",
        "Law office intake specialist receiving a potential client call with AI qualification and attorney handoff",
      ),
      personRole: "Intake specialist",
      environment: "Premium law office",
      workflow: [
        "Potential Client",
        "AI Intake",
        "Case Qualification",
        "Attorney Handoff",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/legal.jpg",
        "Illustration of a legal intake workflow with an inbound call and qualification card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Potential Client",
          subtitle: "Intake line",
          detail: "New matter inquiry",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Intake",
          subtitle: "Qualifying the matter",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Attorney Handoff",
          subtitle: "Case qualified",
          detail: "Context attached",
          meta: "Ready for counsel",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[30%_18%]",
      variant: "hero",
    }),
    "real-estate": industryConfig("real-estate", {
      image: img(
        "/images/human/business/industries/real-estate.jpg",
        "Real estate professional receiving a property inquiry with AI conversation and qualified lead handoff",
      ),
      personRole: "Real estate agent",
      environment: "Modern real estate office",
      workflow: [
        "Property Inquiry",
        "AI Conversation",
        "Lead Qualified",
        "Agent Follow-up",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/real-estate.jpg",
        "Illustration of a real estate inquiry with a call and property lead card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Property Inquiry",
          subtitle: "Listing interest",
          detail: "Inbound prospect",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Conversation",
          subtitle: "Qualifying buyer intent",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Lead Qualified",
          subtitle: "Agent follow-up",
          detail: "Showing preference captured",
          meta: "CRM updated",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[28%_20%]",
      variant: "hero",
    }),
    restaurants: industryConfig("restaurants", {
      image: img(
        "/images/human/business/industries/restaurants.jpg",
        "Restaurant host handling a reservation call with AI receptionist and table confirmation",
      ),
      personRole: "Restaurant host",
      environment: "Premium restaurant host stand",
      workflow: [
        "Incoming Call",
        "AI Receptionist",
        "Table Availability",
        "Reservation Confirmed",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/restaurants.jpg",
        "Illustration of a restaurant reservation call with table availability context",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Incoming Call",
          subtitle: "Reservation line",
          detail: "Party of four",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Receptionist",
          subtitle: "Checking availability",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Reservation Confirmed",
          subtitle: "Table held",
          detail: "Tonight · 7:30 PM",
          meta: "Guest notified",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[30%_22%]",
      variant: "hero",
    }),
    insurance: industryConfig("insurance", {
      image: img(
        "/images/human/business/industries/insurance.jpg",
        "Insurance representative handling a customer inquiry with AI intake and human handoff",
      ),
      personRole: "Insurance representative",
      environment: "Professional insurance office",
      workflow: [
        "Customer Call",
        "AI Intake",
        "Policy Question",
        "Human Representative",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/insurance.jpg",
        "Illustration of an insurance inquiry with a call and intake card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Customer Call",
          subtitle: "Policy question",
          detail: "Service line",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Intake",
          subtitle: "Understanding the request",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Human Representative",
          subtitle: "Context prepared",
          detail: "Ready for handoff",
          meta: "Notes attached",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[28%_18%]",
      variant: "hero",
    }),
    "home-services": industryConfig("home-services", {
      image: img(
        "/images/human/business/industries/home-services.jpg",
        "Home-services dispatcher handling a homeowner call with AI receptionist and technician scheduling",
      ),
      personRole: "Home-services dispatcher",
      environment: "Home-service operations office",
      workflow: [
        "Homeowner Call",
        "AI Receptionist",
        "Service Request",
        "Technician Scheduled",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/home-services.jpg",
        "Illustration of a home-services request with a call and technician scheduling card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Homeowner Call",
          subtitle: "Service request",
          detail: "Inbound job",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Receptionist",
          subtitle: "Capturing the job details",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Technician Scheduled",
          subtitle: "Service calendar",
          detail: "Next available slot",
          meta: "Crew notified",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[30%_20%]",
      variant: "hero",
    }),
    "call-centers": industryConfig("call-centers", {
      image: img(
        "/images/human/business/industries/call-centers.jpg",
        "Contact-center support agent with AI voice routing, intent detection, and human escalation",
      ),
      personRole: "Support agent",
      environment: "Modern contact center",
      workflow: [
        "Incoming Call",
        "AI Voice Agent",
        "Intent Detected",
        "Intelligent Routing",
        "Human Agent",
      ],
      threeDAsset: threeD(
        "/images/3d/industries/call-centers.jpg",
        "Illustration of call-center routing with AI voice handling and human escalation",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Incoming Call",
          subtitle: "Queue signal",
          detail: "Intent pending",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Voice Agent",
          subtitle: "Detecting intent",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Human Escalation",
          subtitle: "Intelligent routing",
          detail: "Context preserved",
          meta: "Agent ready",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[32%_18%]",
      variant: "hero",
    }),
  };

export const useCaseBusinessVisuals: Record<string, HumanBusinessVisualConfig> =
  {
    "appointment-booking": buildUseCaseConfig("appointment-booking", {
      image: img(
        "/images/human/business/use-cases/appointment-booking.jpg",
        "Customer call handled by an AI voice agent that books and confirms an appointment",
      ),
      personRole: "Front-desk professional",
      environment: "Appointment-ready business reception",
      workflow: [
        "Customer",
        "AI Voice Agent",
        "Calendar",
        "Confirmed Appointment",
      ],
      threeDAsset: threeD(
        "/images/3d/use-cases/appointment-booking.jpg",
        "Illustration of appointment booking with a calendar, clock, and voice waveform",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Incoming Call",
          subtitle: "Booking request",
          detail: "Customer line",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Voice Agent",
          subtitle: "Finding an open slot",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Appointment Confirmed",
          subtitle: "Calendar updated",
          detail: "Confirmation ready",
          meta: "Booked",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[26%_24%]",
      variant: "hero",
    }),
    "lead-qualification": buildUseCaseConfig("lead-qualification", {
      image: img(
        "/images/human/business/use-cases/lead-qualification.jpg",
        "Sales professional receiving a CRM lead qualified by an AI phone conversation",
      ),
      personRole: "Sales professional",
      environment: "Modern sales office",
      workflow: [
        "Prospect",
        "AI Conversation",
        "Qualification",
        "CRM Lead",
        "Sales Person",
      ],
      threeDAsset: threeD(
        "/images/3d/use-cases/lead-qualification.jpg",
        "Illustration of lead qualification stages flowing into a contact card",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Prospect Call",
          subtitle: "Inbound interest",
          detail: "Qualification in progress",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Conversation",
          subtitle: "Scoring fit and urgency",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "CRM Lead Ready",
          subtitle: "Sales follow-up",
          detail: "Qualified opportunity",
          meta: "Rep notified",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[30%_18%]",
      variant: "hero",
    }),
    "customer-support": buildUseCaseConfig("customer-support", {
      image: img(
        "/images/human/business/use-cases/customer-support.jpg",
        "Support specialist with AI issue understanding, knowledge context, and human escalation",
      ),
      personRole: "Support specialist",
      environment: "Calm modern support office",
      workflow: [
        "Customer",
        "AI Understands Issue",
        "Knowledge",
        "Resolution",
        "Human Escalation",
      ],
      threeDAsset: threeD(
        "/images/3d/use-cases/customer-support.jpg",
        "Illustration of AI customer support with knowledge layers and a voice interface",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Customer Call",
          subtitle: "Support request",
          detail: "Issue intake",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Support",
          subtitle: "Understanding the issue",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Resolved / Escalated",
          subtitle: "Context preserved",
          detail: "Human ready if needed",
          meta: "Knowledge applied",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[32%_18%]",
      variant: "hero",
    }),
    "call-answering": buildUseCaseConfig("call-answering", {
      image: img(
        "/images/human/business/use-cases/call-answering.jpg",
        "Busy business owner while AI answers the inbound call and captures the customer request",
      ),
      personRole: "Business owner",
      environment: "Busy small-business office",
      workflow: [
        "Incoming Call",
        "AI Receptionist",
        "Customer Request",
        "Business Action",
      ],
      threeDAsset: threeD(
        "/images/3d/use-cases/call-answering.jpg",
        "Illustration of an incoming business phone call with a soft connection waveform",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Incoming Call",
          subtitle: "Never miss a call",
          detail: "Main business line",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Receptionist",
          subtitle: "Answering now",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Business Action",
          subtitle: "Request captured",
          detail: "Ready for follow-up",
          meta: "Covered",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[28%_22%]",
      variant: "hero",
    }),
    "sales-calls": buildUseCaseConfig("sales-calls", {
      image: img(
        "/images/human/business/use-cases/sales-calls.jpg",
        "Salesperson receiving a qualified opportunity after an AI sales conversation",
      ),
      personRole: "Sales representative",
      environment: "Modern sales office",
      workflow: [
        "Prospect",
        "AI Conversation",
        "Qualified Opportunity",
        "Salesperson Receives Lead",
      ],
      threeDAsset: threeD(
        "/images/3d/use-cases/sales-calls.jpg",
        "Illustration of inbound sales calls connected to a CRM-style pipeline",
      ),
      overlayCards: [
        {
          id: "call",
          kind: "incoming-call",
          title: "Prospect Call",
          subtitle: "Sales opportunity",
          detail: "Inbound conversation",
          position: "top-left",
        },
        {
          id: "ai",
          kind: "ai-agent",
          title: "AI Conversation",
          subtitle: "Qualifying the opportunity",
          position: "center",
        },
        {
          id: "outcome",
          kind: "outcome",
          title: "Lead Received",
          subtitle: "Sales follow-up",
          detail: "Qualified opportunity",
          meta: "CRM synced",
          position: "right",
        },
      ],
      bakedOverlays: true,
      focus: "object-[30%_18%]",
      variant: "hero",
    }),
  };

export function getIndustryBusinessVisual(
  slug: string,
): HumanBusinessVisualConfig | null {
  return industryBusinessVisuals[slug] || null;
}

export function getUseCaseBusinessVisual(
  slug: string,
): HumanBusinessVisualConfig | null {
  return useCaseBusinessVisuals[slug] || null;
}

export function getHumanBusinessVisual(
  category: "industry" | "use-case",
  slug: string,
): HumanBusinessVisualConfig | null {
  return category === "industry"
    ? getIndustryBusinessVisual(slug)
    : getUseCaseBusinessVisual(slug);
}
