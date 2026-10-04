/** Premium 3D marketing asset registry and per-page story mappings. */

export type ThreeDAsset = {
  src: string;
  alt: string;
  width: number;
  height: number;
};

const SIZE = { width: 1280, height: 720 } as const;

function asset(
  src: string,
  alt: string,
): ThreeDAsset {
  return { src, alt, ...SIZE };
}

export const threeDCore = {
  aiVoiceAgent: asset(
    "/images/3d/core/ai-voice-agent.jpg",
    "Premium 3D illustration of an AI voice agent interface with a teal waveform and glass microphone",
  ),
  incomingCall: asset(
    "/images/3d/core/incoming-call.jpg",
    "Premium 3D illustration of an incoming business phone call with a soft connection waveform",
  ),
  aiReceptionist: asset(
    "/images/3d/core/ai-receptionist.jpg",
    "Premium 3D illustration of an AI receptionist console with phone, calendar, and voice waveform",
  ),
  appointmentBooking: asset(
    "/images/3d/core/appointment-booking.jpg",
    "Premium 3D illustration of appointment booking with a calendar, clock, and voice waveform",
  ),
  leadQualification: asset(
    "/images/3d/core/lead-qualification.jpg",
    "Premium 3D illustration of lead qualification stages flowing into a CRM-style contact card",
  ),
  customerSupport: asset(
    "/images/3d/core/customer-support.jpg",
    "Premium 3D illustration of AI customer support with knowledge layers and a voice interface",
  ),
  salesCalls: asset(
    "/images/3d/core/sales-calls.jpg",
    "Premium 3D illustration of inbound sales calls connected to a CRM pipeline",
  ),
  humanHandoff: asset(
    "/images/3d/core/human-handoff.jpg",
    "Premium 3D illustration of an AI voice node transferring a call to a human operator console",
  ),
  crmIntegration: asset(
    "/images/3d/core/crm-integration.jpg",
    "Premium 3D illustration of AI voice interaction connected to a CRM contact record",
  ),
  knowledgeBase: asset(
    "/images/3d/core/knowledge-base.jpg",
    "Premium 3D illustration of knowledge documents flowing into an AI voice agent",
  ),
} as const;

export const threeDIndustries: Record<string, ThreeDAsset> = {
  hvac: asset(
    "/images/3d/industries/hvac.jpg",
    "Premium 3D illustration of HVAC service equipment with an incoming call and scheduling card",
  ),
  plumbing: asset(
    "/images/3d/industries/plumbing.jpg",
    "Premium 3D illustration of a plumbing emergency call with dispatch scheduling context",
  ),
  roofing: asset(
    "/images/3d/industries/roofing.jpg",
    "Premium 3D illustration of a roofing estimate request with an inbound call and lead card",
  ),
  electricians: asset(
    "/images/3d/industries/electricians.jpg",
    "Premium 3D illustration of an electrical service request with call and appointment booking",
  ),
  healthcare: asset(
    "/images/3d/industries/healthcare.jpg",
    "Premium 3D illustration of a healthcare clinic patient call and appointment workflow",
  ),
  dental: asset(
    "/images/3d/industries/dental.jpg",
    "Premium 3D illustration of a dental clinic patient booking call with calendar confirmation",
  ),
  legal: asset(
    "/images/3d/industries/legal.jpg",
    "Premium 3D illustration of a law firm consultation call and intake qualification",
  ),
  "real-estate": asset(
    "/images/3d/industries/real-estate.jpg",
    "Premium 3D illustration of a real estate property inquiry call and lead handoff",
  ),
  restaurants: asset(
    "/images/3d/industries/restaurants.jpg",
    "Premium 3D illustration of a restaurant reservation call and table booking workflow",
  ),
  insurance: asset(
    "/images/3d/industries/insurance.jpg",
    "Premium 3D illustration of an insurance customer inquiry and AI intake workflow",
  ),
  "home-services": asset(
    "/images/3d/industries/home-services.jpg",
    "Premium 3D illustration of a home services inbound call with scheduling and dispatch",
  ),
  "call-centers": asset(
    "/images/3d/industries/call-centers.jpg",
    "Premium 3D illustration of multiple inbound calls routed by AI with human escalation",
  ),
};

export const threeDUseCases: Record<string, ThreeDAsset> = {
  "appointment-booking": asset(
    "/images/3d/use-cases/appointment-booking.jpg",
    "Premium 3D illustration of phone booking flowing into a confirmed calendar appointment",
  ),
  "lead-qualification": asset(
    "/images/3d/use-cases/lead-qualification.jpg",
    "Premium 3D illustration of AI lead qualification flowing into a CRM record",
  ),
  "customer-support": asset(
    "/images/3d/use-cases/customer-support.jpg",
    "Premium 3D illustration of AI support resolving a call with knowledge context",
  ),
  "call-answering": asset(
    "/images/3d/use-cases/call-answering.jpg",
    "Premium 3D illustration of an incoming call answered by an AI receptionist",
  ),
  "sales-calls": asset(
    "/images/3d/use-cases/sales-calls.jpg",
    "Premium 3D illustration of an inbound sales call moving into a CRM pipeline",
  ),
};

/** Four story-section assets: spotlight, flow, stack, handoff. */
export function getIndustryStoryAssets(
  slug: string,
): readonly [ThreeDAsset, ThreeDAsset, ThreeDAsset, ThreeDAsset] {
  const industry = threeDIndustries[slug] || threeDCore.aiReceptionist;

  const bySlug: Record<
    string,
    readonly [ThreeDAsset, ThreeDAsset, ThreeDAsset, ThreeDAsset]
  > = {
    hvac: [
      industry,
      threeDCore.aiReceptionist,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    plumbing: [
      industry,
      threeDCore.incomingCall,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    roofing: [
      industry,
      threeDCore.leadQualification,
      threeDCore.appointmentBooking,
      threeDCore.crmIntegration,
    ],
    electricians: [
      industry,
      threeDCore.aiVoiceAgent,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    healthcare: [
      industry,
      threeDCore.aiReceptionist,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    dental: [
      industry,
      threeDCore.aiReceptionist,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    legal: [
      industry,
      threeDCore.leadQualification,
      threeDCore.knowledgeBase,
      threeDCore.humanHandoff,
    ],
    "real-estate": [
      industry,
      threeDCore.leadQualification,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    restaurants: [
      industry,
      threeDCore.incomingCall,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    insurance: [
      industry,
      threeDCore.leadQualification,
      threeDCore.crmIntegration,
      threeDCore.humanHandoff,
    ],
    "home-services": [
      industry,
      threeDCore.aiReceptionist,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    "call-centers": [
      industry,
      threeDCore.aiVoiceAgent,
      threeDCore.knowledgeBase,
      threeDCore.humanHandoff,
    ],
  };

  return (
    bySlug[slug] || [
      industry,
      threeDCore.aiVoiceAgent,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ]
  );
}

export function getUseCaseStoryAssets(
  slug: string,
): readonly [ThreeDAsset, ThreeDAsset, ThreeDAsset, ThreeDAsset] {
  const primary = threeDUseCases[slug] || threeDCore.aiVoiceAgent;

  const bySlug: Record<
    string,
    readonly [ThreeDAsset, ThreeDAsset, ThreeDAsset, ThreeDAsset]
  > = {
    "appointment-booking": [
      threeDCore.incomingCall,
      threeDCore.aiVoiceAgent,
      threeDCore.appointmentBooking,
      threeDCore.humanHandoff,
    ],
    "lead-qualification": [
      threeDCore.incomingCall,
      threeDCore.leadQualification,
      threeDCore.crmIntegration,
      threeDCore.humanHandoff,
    ],
    "customer-support": [
      threeDCore.incomingCall,
      threeDCore.customerSupport,
      threeDCore.knowledgeBase,
      threeDCore.humanHandoff,
    ],
    "call-answering": [
      threeDCore.incomingCall,
      threeDCore.aiReceptionist,
      threeDCore.aiVoiceAgent,
      threeDCore.humanHandoff,
    ],
    "sales-calls": [
      threeDCore.incomingCall,
      threeDCore.salesCalls,
      threeDCore.crmIntegration,
      threeDCore.humanHandoff,
    ],
  };

  return (
    bySlug[slug] || [
      primary,
      threeDCore.aiVoiceAgent,
      threeDCore.crmIntegration,
      threeDCore.humanHandoff,
    ]
  );
}

export function getIndustryHeroAsset(slug: string): ThreeDAsset {
  return threeDIndustries[slug] || threeDCore.aiReceptionist;
}

export function getUseCaseHeroAsset(slug: string): ThreeDAsset {
  return threeDUseCases[slug] || threeDCore.aiVoiceAgent;
}
