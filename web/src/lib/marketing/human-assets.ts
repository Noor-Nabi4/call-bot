/** Human business-scene photography registry and story composition mappings. */

export type HumanAsset = {
  src: string;
  alt: string;
  width: number;
  height: number;
};

export type StoryMediaComposition =
  | "human-product"
  | "three-d"
  | "human-3d"
  | "human-handoff";

export type StoryMediaAsset = {
  src: string;
  alt: string;
  width: number;
  height: number;
};

export type StoryMedia = {
  composition: StoryMediaComposition;
  human?: HumanAsset;
  threeD?: StoryMediaAsset;
};

const SIZE = { width: 1280, height: 720 } as const;

function asset(src: string, alt: string): HumanAsset {
  return { src, alt, ...SIZE };
}

function threeD(src: string, alt: string): StoryMediaAsset {
  return { src, alt, ...SIZE };
}

/** Local 3D path refs so this module stays importable under node tests. */
const d3 = {
  aiVoiceAgent: threeD(
    "/images/3d/core/ai-voice-agent.jpg",
    "AI voice agent interface with a teal waveform and glass microphone",
  ),
  incomingCall: threeD(
    "/images/3d/core/incoming-call.jpg",
    "Incoming business phone call with a soft connection waveform",
  ),
  aiReceptionist: threeD(
    "/images/3d/core/ai-receptionist.jpg",
    "AI receptionist console with phone, calendar, and voice waveform",
  ),
  appointmentBooking: threeD(
    "/images/3d/core/appointment-booking.jpg",
    "Appointment booking with a calendar, clock, and voice waveform",
  ),
  leadQualification: threeD(
    "/images/3d/core/lead-qualification.jpg",
    "Lead qualification stages flowing into a CRM-style contact card",
  ),
  customerSupport: threeD(
    "/images/3d/core/customer-support.jpg",
    "AI customer support with knowledge layers and a voice interface",
  ),
  salesCalls: threeD(
    "/images/3d/core/sales-calls.jpg",
    "Inbound sales calls connected to a CRM-style pipeline",
  ),
  humanHandoff: threeD(
    "/images/3d/core/human-handoff.jpg",
    "AI voice node transferring a call to a human operator console",
  ),
  crmIntegration: threeD(
    "/images/3d/core/crm-integration.jpg",
    "AI voice interaction connected to a CRM contact record",
  ),
  knowledgeBase: threeD(
    "/images/3d/core/knowledge-base.jpg",
    "Knowledge documents flowing into an AI voice agent",
  ),
  industry: (slug: string) =>
    threeD(
      `/images/3d/industries/${slug}.jpg`,
      `${slug.replace(/-/g, " ")} workflow with call and business-action context`,
    ),
  useCase: (slug: string) =>
    threeD(
      `/images/3d/use-cases/${slug}.jpg`,
      `${slug.replace(/-/g, " ")} workflow with call and outcome context`,
    ),
} as const;

export const humanCore = {
  businessOwnerCall: asset(
    "/images/human/core/business-owner-call.jpg",
    "Small-business owner taking a customer phone call in a modern office",
  ),
  receptionistDesk: asset(
    "/images/human/core/receptionist-desk.jpg",
    "Receptionist at a front desk handling an inbound call with a headset",
  ),
  customerCalling: asset(
    "/images/human/core/customer-calling.jpg",
    "Customer calling a local business on a smartphone",
  ),
  handoffAgent: asset(
    "/images/human/core/handoff-agent.jpg",
    "Office employee receiving a transferred call at a workstation",
  ),
  salesLead: asset(
    "/images/human/core/sales-lead.jpg",
    "Sales professional reviewing a newly qualified inbound lead",
  ),
  supportEscalation: asset(
    "/images/human/core/support-escalation.jpg",
    "Customer support specialist handling an escalated call with a headset",
  ),
  opsConsole: asset(
    "/images/human/core/ops-console.jpg",
    "Business operator reviewing call activity on a laptop",
  ),
  appointmentBooking: asset(
    "/images/human/core/appointment-booking.jpg",
    "Front-desk professional confirming an appointment while on a call",
  ),
} as const;

/** Campaign scene refs (same files as `human-business-visuals`). */
export const humanIndustries: Record<string, HumanAsset> = {
  hvac: asset(
    "/images/human/business/industries/hvac.jpg",
    "HVAC dispatcher handling an inbound service call with AI receptionist and technician scheduling",
  ),
  plumbing: asset(
    "/images/human/business/industries/plumbing.jpg",
    "Plumbing company dispatcher on a customer service call with AI triage and plumber dispatch",
  ),
  roofing: asset(
    "/images/human/business/industries/roofing.jpg",
    "Roofing office professional receiving a homeowner inquiry with AI lead qualification",
  ),
  electricians: asset(
    "/images/human/business/industries/electricians.jpg",
    "Electrical service dispatcher answering a customer call with AI issue capture and technician assignment",
  ),
  healthcare: asset(
    "/images/human/business/industries/healthcare.jpg",
    "Clinic receptionist handling a patient call with AI receptionist and appointment coordination",
  ),
  dental: asset(
    "/images/human/business/industries/dental.jpg",
    "Dental receptionist answering a patient call with AI receptionist and appointment confirmation",
  ),
  legal: asset(
    "/images/human/business/industries/legal.jpg",
    "Law office intake specialist receiving a potential client call with AI qualification and attorney handoff",
  ),
  "real-estate": asset(
    "/images/human/business/industries/real-estate.jpg",
    "Real estate professional receiving a property inquiry with AI conversation and qualified lead handoff",
  ),
  restaurants: asset(
    "/images/human/business/industries/restaurants.jpg",
    "Restaurant host handling a reservation call with AI receptionist and table confirmation",
  ),
  insurance: asset(
    "/images/human/business/industries/insurance.jpg",
    "Insurance representative handling a customer inquiry with AI intake and human handoff",
  ),
  "home-services": asset(
    "/images/human/business/industries/home-services.jpg",
    "Home-services dispatcher handling a homeowner call with AI receptionist and technician scheduling",
  ),
  "call-centers": asset(
    "/images/human/business/industries/call-centers.jpg",
    "Contact-center support agent with AI voice routing, intent detection, and human escalation",
  ),
};

export const humanUseCases: Record<string, HumanAsset> = {
  "appointment-booking": asset(
    "/images/human/business/use-cases/appointment-booking.jpg",
    "Customer call handled by an AI voice agent that books and confirms an appointment",
  ),
  "lead-qualification": asset(
    "/images/human/business/use-cases/lead-qualification.jpg",
    "Sales professional receiving a CRM lead qualified by an AI phone conversation",
  ),
  "customer-support": asset(
    "/images/human/business/use-cases/customer-support.jpg",
    "Support specialist with AI issue understanding, knowledge context, and human escalation",
  ),
  "call-answering": asset(
    "/images/human/business/use-cases/call-answering.jpg",
    "Busy business owner while AI answers the inbound call and captures the customer request",
  ),
  "sales-calls": asset(
    "/images/human/business/use-cases/sales-calls.jpg",
    "Salesperson receiving a qualified opportunity after an AI sales conversation",
  ),
};

export function getIndustryHumanHero(slug: string): HumanAsset {
  return humanIndustries[slug] || humanCore.receptionistDesk;
}

export function getUseCaseHumanHero(slug: string): HumanAsset {
  return humanUseCases[slug] || humanCore.customerCalling;
}

/**
 * Four-section media rhythm:
 * 1 human+product · 2 three-d workflow · 3 human+3d · 4 human handoff
 */
export function getIndustryStoryMedia(
  slug: string,
): readonly [StoryMedia, StoryMedia, StoryMedia, StoryMedia] {
  const human = getIndustryHumanHero(slug);
  const industry3d = d3.industry(slug);

  const bookingOrCrm =
    slug === "legal" ||
    slug === "insurance" ||
    slug === "roofing" ||
    slug === "call-centers"
      ? d3.crmIntegration
      : d3.appointmentBooking;

  const flow3d =
    slug === "call-centers"
      ? d3.aiVoiceAgent
      : slug === "legal" || slug === "insurance" || slug === "roofing"
        ? d3.leadQualification
        : d3.aiReceptionist;

  return [
    {
      composition: "human-product",
      human,
      threeD: industry3d,
    },
    {
      composition: "three-d",
      threeD: flow3d,
    },
    {
      composition: "human-3d",
      human:
        slug === "dental" || slug === "healthcare"
          ? humanCore.appointmentBooking
          : humanCore.opsConsole,
      threeD: bookingOrCrm,
    },
    {
      composition: "human-handoff",
      human:
        slug === "call-centers"
          ? humanCore.supportEscalation
          : slug === "real-estate" || slug === "roofing" || slug === "legal"
            ? humanCore.salesLead
            : humanCore.handoffAgent,
      threeD: d3.humanHandoff,
    },
  ];
}

export function getUseCaseStoryMedia(
  slug: string,
): readonly [StoryMedia, StoryMedia, StoryMedia, StoryMedia] {
  const human = getUseCaseHumanHero(slug);

  const bySlug: Record<
    string,
    readonly [StoryMedia, StoryMedia, StoryMedia, StoryMedia]
  > = {
    "appointment-booking": [
      {
        composition: "human-product",
        human: humanCore.customerCalling,
        threeD: d3.incomingCall,
      },
      { composition: "three-d", threeD: d3.aiVoiceAgent },
      {
        composition: "human-3d",
        human: humanCore.appointmentBooking,
        threeD: d3.appointmentBooking,
      },
      {
        composition: "human-handoff",
        human: humanCore.handoffAgent,
        threeD: d3.humanHandoff,
      },
    ],
    "lead-qualification": [
      {
        composition: "human-product",
        human: humanCore.customerCalling,
        threeD: d3.incomingCall,
      },
      { composition: "three-d", threeD: d3.leadQualification },
      {
        composition: "human-3d",
        human: humanCore.salesLead,
        threeD: d3.crmIntegration,
      },
      {
        composition: "human-handoff",
        human: humanCore.salesLead,
        threeD: d3.humanHandoff,
      },
    ],
    "customer-support": [
      {
        composition: "human-product",
        human: humanCore.customerCalling,
        threeD: d3.incomingCall,
      },
      { composition: "three-d", threeD: d3.customerSupport },
      {
        composition: "human-3d",
        human: humanCore.supportEscalation,
        threeD: d3.knowledgeBase,
      },
      {
        composition: "human-handoff",
        human: humanCore.supportEscalation,
        threeD: d3.humanHandoff,
      },
    ],
    "call-answering": [
      {
        composition: "human-product",
        human: humanCore.customerCalling,
        threeD: d3.incomingCall,
      },
      { composition: "three-d", threeD: d3.aiReceptionist },
      {
        composition: "human-3d",
        human: humanCore.receptionistDesk,
        threeD: d3.aiVoiceAgent,
      },
      {
        composition: "human-handoff",
        human: humanCore.businessOwnerCall,
        threeD: d3.humanHandoff,
      },
    ],
    "sales-calls": [
      {
        composition: "human-product",
        human: humanCore.customerCalling,
        threeD: d3.incomingCall,
      },
      { composition: "three-d", threeD: d3.salesCalls },
      {
        composition: "human-3d",
        human: humanCore.salesLead,
        threeD: d3.crmIntegration,
      },
      {
        composition: "human-handoff",
        human: humanCore.salesLead,
        threeD: d3.humanHandoff,
      },
    ],
  };

  return (
    bySlug[slug] || [
      {
        composition: "human-product",
        human,
        threeD: d3.useCase(slug),
      },
      { composition: "three-d", threeD: d3.aiVoiceAgent },
      {
        composition: "human-3d",
        human: humanCore.opsConsole,
        threeD: d3.crmIntegration,
      },
      {
        composition: "human-handoff",
        human: humanCore.handoffAgent,
        threeD: d3.humanHandoff,
      },
    ]
  );
}
