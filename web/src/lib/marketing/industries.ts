/** Unique industry landing content for US commercial SEO. */

export type IndustryPage = {
  slug: string;
  name: string;
  shortName: string;
  navLabel: string;
  title: string;
  description: string;
  h1: string;
  eyebrow: string;
  supporting: string;
  problems: readonly { title: string; body: string }[];
  scenarios: readonly { title: string; body: string }[];
  workflows: readonly { title: string; body: string }[];
  benefits: readonly { title: string; body: string }[];
  faqs: readonly { question: string; answer: string }[];
  relatedSlugs: readonly string[];
  useCaseHrefs: readonly string[];
  keywords: readonly string[];
};

export const industriesHub = {
  title: "AI Voice Agents by Industry",
  description:
    "See how Call & Flow AI receptionists and voice agents handle calls for home services, healthcare, legal, real estate, restaurants, and more.",
  h1: "AI Voice Agents Built for Your Industry",
  supporting:
    "Every industry has different callers, urgency, and booking rules. Start from a template shaped around how your customers actually call — then customize greeting, knowledge, and handoff.",
} as const;

export const industryPages: readonly IndustryPage[] = [
  {
    slug: "hvac",
    name: "HVAC",
    shortName: "HVAC companies",
    navLabel: "HVAC",
    title: "AI Receptionist for HVAC Companies",
    description:
      "AI receptionist for HVAC companies that answers service calls, books appointments, captures emergency requests, and routes urgent jobs after hours.",
    h1: "AI Receptionist for HVAC Companies",
    eyebrow: "HVAC & climate control",
    supporting:
      "When AC dies in July or a furnace fails overnight, callers expect a fast answer. Call & Flow answers the phone, qualifies the job, and books service so your dispatch board stays full.",
    problems: [
      {
        title: "Missed calls become lost jobs",
        body: "Homeowners calling about no heat or no cool rarely leave a long voicemail. If you miss the first ring, they dial the next contractor on the list.",
      },
      {
        title: "Peak season overwhelms the front desk",
        body: "Summer and winter spikes flood the line while techs are already on the road. One person cannot answer every estimate, warranty, and emergency call.",
      },
      {
        title: "After-hours emergencies need triage",
        body: "Not every midnight call is a true emergency — but some are. You need consistent intake that captures address, symptoms, and urgency without waking the whole office.",
      },
    ],
    scenarios: [
      {
        title: "No-cool emergency",
        body: "Caller reports no AC, shares address and system age, and gets next available emergency or same-day options based on your rules.",
      },
      {
        title: "Maintenance plan booking",
        body: "Existing customer wants a tune-up. The agent confirms the account, offers open slots, and books the appointment.",
      },
      {
        title: "Estimate request",
        body: "New lead asks about a heat pump quote. The agent captures contact info, property details, and preferred callback window.",
      },
    ],
    workflows: [
      {
        title: "Never miss an HVAC lead",
        body: "Inbound calls are answered even when the office line is busy, so estimate and repair requests are captured on the first try.",
      },
      {
        title: "Answer emergency service calls",
        body: "Urgent language — no heat, gas smell, frozen pipes nearby — can trigger priority routing or after-hours escalation rules you define.",
      },
      {
        title: "Schedule appointments",
        body: "Offer real availability for diagnostics, installs, and maintenance instead of promising a callback that never happens.",
      },
      {
        title: "Qualify service requests",
        body: "Collect system type, symptoms, service area, and preferred timing before a dispatcher or sales rep follows up.",
      },
      {
        title: "Capture customer information",
        body: "Name, phone, address, and issue notes land in one place so your team is not starting from a sticky note.",
      },
      {
        title: "Route urgent calls",
        body: "When a human is required, transfer or queue a callback with the full call summary attached.",
      },
      {
        title: "After-hours answering",
        body: "Overnight callers get help booking next-day service or reaching on-call staff according to your playbook.",
      },
      {
        title: "Human escalation",
        body: "Warranty disputes, billing questions, and complex installs escalate cleanly instead of looping in a chatbot.",
      },
    ],
    benefits: [
      {
        title: "Keep the dispatch board fed",
        body: "More answered calls mean more booked diagnostics and fewer empty tech days during shoulder season.",
      },
      {
        title: "Protect peak-season capacity",
        body: "Let AI handle FAQs and booking while your CSR focuses on high-value installs and upset customers.",
      },
      {
        title: "Consistent intake every time",
        body: "Every caller is asked the same critical questions — address, symptoms, access notes — so techs arrive prepared.",
      },
    ],
    faqs: [
      {
        question: "Can an AI receptionist handle HVAC emergency calls?",
        answer:
          "Yes. You define what counts as urgent. Call & Flow can collect details, book the next available slot, or escalate to on-call staff when transfer is available.",
      },
      {
        question: "Will it invent service pricing?",
        answer:
          "No. Agents answer from your approved knowledge and booking rules. If a price is not documented, they take a message or offer an estimate appointment.",
      },
      {
        question: "Does it work for multi-location HVAC companies?",
        answer:
          "Yes. Use separate numbers, knowledge, and routing rules per location or brand while keeping one operations console.",
      },
    ],
    relatedSlugs: ["plumbing", "electricians", "home-services", "roofing"],
    useCaseHrefs: [
      "/use-cases/call-answering",
      "/use-cases/appointment-booking",
      "/use-cases/lead-qualification",
    ],
    keywords: [
      "AI receptionist for HVAC",
      "HVAC answering service",
      "AI phone agent HVAC",
    ],
  },
  {
    slug: "plumbing",
    name: "Plumbing",
    shortName: "plumbing companies",
    navLabel: "Plumbing",
    title: "AI Receptionist for Plumbing Companies",
    description:
      "AI receptionist for plumbers that answers leak and clog calls, books service, qualifies emergencies, and covers the phones after hours.",
    h1: "AI Receptionist for Plumbing Companies",
    eyebrow: "Plumbing & drain",
    supporting:
      "Water does not wait for business hours. Call & Flow answers leak, clog, and water-heater calls, captures the address, and gets the right urgency in front of your team.",
    problems: [
      {
        title: "Active leaks need immediate intake",
        body: "Callers with a burst pipe need someone who can capture the address and severity fast — not a voicemail box.",
      },
      {
        title: "CSR time is eaten by routine questions",
        body: "Hours, service area, and “do you do water heaters?” calls stack up while high-urgency jobs wait.",
      },
      {
        title: "Night and weekend overflow",
        body: "Many plumbing emergencies happen when the office is closed. Missed after-hours calls are lost revenue and damaged homes.",
      },
    ],
    scenarios: [
      {
        title: "Active leak triage",
        body: "Caller describes water at the ceiling. The agent captures location, shutoff status if known, and routes for emergency response.",
      },
      {
        title: "Drain cleaning booking",
        body: "Homeowner wants a clog cleared. The agent confirms service area and books a standard service window.",
      },
      {
        title: "Water heater replacement lead",
        body: "Lead wants a quote. Contact details, tank vs tankless preference, and preferred visit time are captured for sales follow-up.",
      },
    ],
    workflows: [
      {
        title: "Emergency vs standard split",
        body: "Use your rules to separate active flooding from non-urgent fixture installs so dispatch prioritizes correctly.",
      },
      {
        title: "Service-area checks",
        body: "Confirm the caller is inside your coverage area before promising a truck.",
      },
      {
        title: "Appointment booking",
        body: "Book diagnostics and installs into real availability your office already trusts.",
      },
      {
        title: "Lead capture for replacements",
        body: "Water heater and repipe inquiries become structured leads instead of half-heard phone notes.",
      },
      {
        title: "After-hours coverage",
        body: "Answer overnight emergencies and book first-available morning slots when on-call transfer is off.",
      },
      {
        title: "Human handoff",
        body: "Escalate billing disputes, insurance jobs, and complex commercial work to a person with context.",
      },
    ],
    benefits: [
      {
        title: "Faster emergency intake",
        body: "Critical details are collected consistently so techs know what they are walking into.",
      },
      {
        title: "Fewer missed after-hours jobs",
        body: "Overnight callers get a real conversation and a clear next step.",
      },
      {
        title: "Cleaner sales handoff",
        body: "Replacement and remodel leads arrive with the questions already answered.",
      },
    ],
    faqs: [
      {
        question: "Can AI tell if a plumbing call is an emergency?",
        answer:
          "It follows the emergency criteria you configure — for example active leaks, no water, or sewage backup — then books or escalates accordingly.",
      },
      {
        question: "Can it handle commercial plumbing inquiries?",
        answer:
          "Yes. You can tailor knowledge and routing for residential vs commercial lines, or use separate numbers for each.",
      },
      {
        question: "Will callers know they are talking to AI?",
        answer:
          "You control the greeting and brand voice. Many businesses introduce the agent as their virtual receptionist; others keep the experience conversational and brand-forward.",
      },
    ],
    relatedSlugs: ["hvac", "electricians", "home-services", "roofing"],
    useCaseHrefs: [
      "/use-cases/call-answering",
      "/use-cases/appointment-booking",
      "/use-cases/lead-qualification",
    ],
    keywords: [
      "AI receptionist for plumbers",
      "plumbing answering service",
      "AI phone agent plumbing",
    ],
  },
  {
    slug: "roofing",
    name: "Roofing",
    shortName: "roofing companies",
    navLabel: "Roofing",
    title: "AI Receptionist for Roofing Companies",
    description:
      "AI receptionist for roofers that qualifies storm damage leads, books inspections, answers FAQs, and keeps sales follow-up moving after storms.",
    h1: "AI Receptionist for Roofing Companies",
    eyebrow: "Roofing & exterior",
    supporting:
      "After a hailstorm, your phones do not stop. Call & Flow answers inspection requests, qualifies insurance jobs, and books roof assessments before competitors do.",
    problems: [
      {
        title: "Storm spikes overwhelm sales",
        body: "A single weather event can dump hundreds of inspection requests. Missed rings mean lost insurance work.",
      },
      {
        title: "Lead quality varies wildly",
        body: "Not every caller is ready for a full roof replacement. Your team needs basic qualification before rolling a truck.",
      },
      {
        title: "Callbacks get buried",
        body: "When the office is slammed, inspection leads sit in voicemail while homeowners book someone else.",
      },
    ],
    scenarios: [
      {
        title: "Storm damage inspection",
        body: "Homeowner reports hail. The agent captures address, insurance status if shared, and books an inspection window.",
      },
      {
        title: "Leak investigation",
        body: "Caller has an active leak. Urgency is noted and a diagnostic visit is scheduled or escalated.",
      },
      {
        title: "Retail reroof quote",
        body: "Non-storm lead wants pricing. Contact info, roof age, and preferred consult time are captured for the sales team.",
      },
    ],
    workflows: [
      {
        title: "Inspection booking at scale",
        body: "Keep booking even when the sales floor is out measuring roofs.",
      },
      {
        title: "Insurance job intake",
        body: "Ask the qualification questions your estimators need before the first site visit.",
      },
      {
        title: "FAQ deflection",
        body: "Answer financing, materials, and service-area questions from your knowledge base.",
      },
      {
        title: "Sales handoff",
        body: "Qualified leads land with notes so closers spend time selling, not re-asking basics.",
      },
      {
        title: "After-storm overflow",
        body: "Handle spike volume without hiring a temporary call center for two weeks.",
      },
      {
        title: "Human escalation",
        body: "Angry callback or complex commercial bid? Transfer with the conversation summary attached.",
      },
    ],
    benefits: [
      {
        title: "Capture storm demand",
        body: "Answer more inspection requests during the window when homeowners are ready to act.",
      },
      {
        title: "Better-qualified site visits",
        body: "Estimators arrive knowing property details and caller intent.",
      },
      {
        title: "Steady retail pipeline",
        body: "Non-storm reroof leads keep flowing even when marketing is quiet.",
      },
    ],
    faqs: [
      {
        question: "Can an AI receptionist book roof inspections?",
        answer:
          "Yes. Connect your availability rules and the agent can offer real inspection slots and confirm caller details.",
      },
      {
        question: "Does it handle insurance claim questions?",
        answer:
          "It can explain your documented process and collect claim-related details you approve. It should not invent adjuster advice or coverage promises.",
      },
      {
        question: "Is this useful outside storm season?",
        answer:
          "Yes. Leak calls, maintenance questions, and retail replacements still need reliable phone coverage year-round.",
      },
    ],
    relatedSlugs: ["home-services", "hvac", "real-estate", "insurance"],
    useCaseHrefs: [
      "/use-cases/lead-qualification",
      "/use-cases/appointment-booking",
      "/use-cases/sales-calls",
    ],
    keywords: [
      "AI receptionist for roofing",
      "roofing answering service",
      "AI phone agent roofers",
    ],
  },
  {
    slug: "electricians",
    name: "Electricians",
    shortName: "electrical contractors",
    navLabel: "Electricians",
    title: "AI Receptionist for Electricians",
    description:
      "AI receptionist for electrical contractors that answers service calls, books panel and outlet jobs, and routes safety-related emergencies.",
    h1: "AI Receptionist for Electricians",
    eyebrow: "Electrical contractors",
    supporting:
      "From tripped breakers to EV charger installs, electrical callers need clear next steps. Call & Flow answers, qualifies, and books so your electricians stay productive in the field.",
    problems: [
      {
        title: "Safety language needs careful handling",
        body: "Burning smells and sparking outlets require urgent, consistent intake — not a casual “we’ll call you back.”",
      },
      {
        title: "Install leads need qualification",
        body: "EV chargers, panels, and generator work need property details before a profitable site visit.",
      },
      {
        title: "Office coverage gaps",
        body: "Owner-operators often answer between jobs. Missed midday calls are missed revenue.",
      },
    ],
    scenarios: [
      {
        title: "Power outage / breaker issues",
        body: "Caller has partial power. The agent gathers symptoms and books a diagnostic or escalates if safety keywords appear.",
      },
      {
        title: "EV charger install lead",
        body: "Capture vehicle type, panel info if known, and preferred consult time for the sales or estimating team.",
      },
      {
        title: "Commercial tenant build-out",
        body: "Property manager inquiry is logged with site details and routed to commercial sales.",
      },
    ],
    workflows: [
      {
        title: "Safety-first intake",
        body: "Configure escalation for burning smell, sparking, or flooding near electrical equipment.",
      },
      {
        title: "Service booking",
        body: "Book standard repairs and troubleshooting into open schedule windows.",
      },
      {
        title: "Install qualification",
        body: "Collect the details estimators need for panels, lighting, and EV work.",
      },
      {
        title: "Knowledge answers",
        body: "Explain licensing, service area, and process from approved documents.",
      },
      {
        title: "After-hours answering",
        body: "Capture night emergencies and morning booking requests without missing the lead.",
      },
      {
        title: "Human transfer",
        body: "Move complex commercial or code questions to a licensed team member with context.",
      },
    ],
    benefits: [
      {
        title: "Protect high-margin installs",
        body: "EV and panel leads are captured completely, not lost to voicemail.",
      },
      {
        title: "Consistent emergency response",
        body: "Urgent calls follow the same checklist every time.",
      },
      {
        title: "Owner-operator freedom",
        body: "Stay on the tools while the phone still gets answered professionally.",
      },
    ],
    faqs: [
      {
        question: "Can AI give electrical advice?",
        answer:
          "No clinical or code advice beyond your approved knowledge. For safety issues, it collects details and escalates according to your rules.",
      },
      {
        question: "Can it book both residential and commercial jobs?",
        answer:
          "Yes. Use different prompts, numbers, or routing rules if residential and commercial flows differ.",
      },
      {
        question: "Does Call & Flow replace my dispatcher?",
        answer:
          "It handles front-line answering and booking so dispatchers spend time assigning work, not repeating the same intake questions.",
      },
    ],
    relatedSlugs: ["hvac", "plumbing", "home-services", "call-centers"],
    useCaseHrefs: [
      "/use-cases/call-answering",
      "/use-cases/appointment-booking",
      "/use-cases/lead-qualification",
    ],
    keywords: [
      "AI receptionist for electricians",
      "electrical contractor answering service",
      "AI phone agent electrician",
    ],
  },
  {
    slug: "healthcare",
    name: "Healthcare",
    shortName: "healthcare clinics",
    navLabel: "Healthcare",
    title: "AI Receptionist for Healthcare Clinics",
    description:
      "AI receptionist for healthcare clinics that covers front-desk calls, helps with scheduling, answers non-clinical FAQs, and escalates urgent patient needs.",
    h1: "AI Receptionist for Healthcare Clinics",
    eyebrow: "Healthcare & clinics",
    supporting:
      "Front desks are overloaded with scheduling, insurance questions, and routine FAQs. Call & Flow covers the phones for hours and booking — without inventing clinical advice.",
    problems: [
      {
        title: "Hold times frustrate patients",
        body: "Long rings and voicemail drive patients to portals, competitors, or no-shows that never get rescheduled.",
      },
      {
        title: "Staff juggle phones and check-in",
        body: "When the lobby is busy, inbound calls suffer. Clinics need coverage that does not pull medical assistants off the floor.",
      },
      {
        title: "Urgent symptoms need careful escalation",
        body: "Phone automation must never play doctor — but it can follow your escalation script for chest pain, breathing issues, or after-hours nurse lines.",
      },
    ],
    scenarios: [
      {
        title: "New patient scheduling",
        body: "Caller wants a first available appointment. The agent collects basics and books according to your scheduling rules.",
      },
      {
        title: "Hours and location FAQ",
        body: "Patient asks about parking, hours, or forms. Answers come from your approved knowledge base.",
      },
      {
        title: "Urgent symptom escalation",
        body: "Caller describes urgent symptoms. The agent follows your script to escalate or direct to emergency services as configured — never diagnosing.",
      },
    ],
    workflows: [
      {
        title: "Front-desk call coverage",
        body: "Answer routine scheduling and FAQ calls so staff can focus on in-clinic patients.",
      },
      {
        title: "Appointment booking support",
        body: "Offer availability based on rules you control. Confirm details before saving the visit.",
      },
      {
        title: "Non-clinical FAQ answers",
        body: "Hours, directions, accepted insurance lists you publish, and preparation instructions from approved documents.",
      },
      {
        title: "After-hours messaging",
        body: "Capture callback requests and urgent escalations according to your clinic policy.",
      },
      {
        title: "Human handoff",
        body: "Billing specialists, nurses, or providers receive transfers with a clear summary.",
      },
      {
        title: "Multi-location routing",
        body: "Route by clinic location or department when you use multiple numbers.",
      },
    ],
    benefits: [
      {
        title: "Lower abandoned call rates",
        body: "Patients reach a helpful voice instead of endless hold music.",
      },
      {
        title: "Protect clinical staff time",
        body: "Routine phone work stops interrupting rooming and procedures.",
      },
      {
        title: "Policy-safe automation",
        body: "No invented diagnoses — only your approved knowledge and escalation paths.",
      },
    ],
    faqs: [
      {
        question: "Is Call & Flow a medical device or clinical advisor?",
        answer:
          "No. It is a business phone automation platform. It must not diagnose or invent clinical guidance. Urgent scenarios follow scripts you approve.",
      },
      {
        question: "Can it integrate with our EHR scheduling?",
        answer:
          "Booking behavior depends on the scheduling rules and integrations available in your workspace. Start with Call & Flow appointment flows and expand integrations as configured.",
      },
      {
        question: "Can it handle HIPAA considerations?",
        answer:
          "Discuss compliance, BAAs, and data handling with our team for your deployment. Do not put sensitive clinical content in unapproved knowledge documents.",
      },
    ],
    relatedSlugs: ["dental", "insurance", "call-centers", "home-services"],
    useCaseHrefs: [
      "/use-cases/appointment-booking",
      "/use-cases/customer-support",
      "/use-cases/call-answering",
    ],
    keywords: [
      "AI receptionist for healthcare",
      "clinic phone answering AI",
      "AI voice agent medical office",
    ],
  },
  {
    slug: "dental",
    name: "Dental",
    shortName: "dental practices",
    navLabel: "Dental",
    title: "AI Receptionist for Dental Practices",
    description:
      "AI receptionist for dental offices that books cleanings and consults, answers insurance FAQs you approve, and reduces front-desk phone load.",
    h1: "AI Receptionist for Dental Practices",
    eyebrow: "Dental practices",
    supporting:
      "Your front desk should greet patients in the lobby — not live on hold. Call & Flow books hygiene visits, captures new-patient details, and answers the questions you publish.",
    problems: [
      {
        title: "New-patient calls go to voicemail",
        body: "Shoppers calling for a cleaning or consult often hang up if nobody answers. Those patients book elsewhere.",
      },
      {
        title: "Confirmations eat the day",
        body: "Reschedules, hours questions, and insurance FAQs keep the front desk from chairside coordination.",
      },
      {
        title: "Lunch and after-hours gaps",
        body: "Midday and evening callers still expect an answer, especially for tooth pain.",
      },
    ],
    scenarios: [
      {
        title: "Hygiene booking",
        body: "Existing patient wants a cleaning. The agent offers open slots and confirms the appointment.",
      },
      {
        title: "New patient intake",
        body: "Caller needs a first visit. Contact details, preferred times, and reason for visit are captured.",
      },
      {
        title: "Tooth pain after hours",
        body: "Urgent dental pain follows your escalation or next-day emergency slot rules — without clinical diagnosis.",
      },
    ],
    workflows: [
      {
        title: "Appointment booking",
        body: "Book cleanings, exams, and consults into real availability.",
      },
      {
        title: "New patient qualification",
        body: "Collect insurance info only as you allow, plus preferred provider and timing.",
      },
      {
        title: "Approved FAQ answers",
        body: "Hours, parking, financing pages you approve, and prep instructions.",
      },
      {
        title: "No-show recovery support",
        body: "Make it easy for patients who missed a visit to rebook quickly.",
      },
      {
        title: "After-hours coverage",
        body: "Capture pain calls and morning openings when the office is closed.",
      },
      {
        title: "Front-desk handoff",
        body: "Transfer billing or treatment-plan questions to staff with a summary.",
      },
    ],
    benefits: [
      {
        title: "Fill the hygiene schedule",
        body: "More answered calls mean fewer empty chairs.",
      },
      {
        title: "Calmer front desk",
        body: "Staff can focus on patients in the office instead of juggling every ring.",
      },
      {
        title: "Better new-patient experience",
        body: "First impressions start with a helpful, on-brand phone answer.",
      },
    ],
    faqs: [
      {
        question: "Can an AI receptionist book dental appointments?",
        answer:
          "Yes. With your scheduling rules connected, it can offer open times and confirm patient details before saving the visit.",
      },
      {
        question: "Will it give dental advice?",
        answer:
          "No. It answers operational FAQs from your knowledge and escalates symptom-related calls per your script.",
      },
      {
        question: "Can multi-doctor practices use it?",
        answer:
          "Yes. Route by provider preference, location, or appointment type based on how you configure the agent.",
      },
    ],
    relatedSlugs: ["healthcare", "insurance", "call-centers"],
    useCaseHrefs: [
      "/use-cases/appointment-booking",
      "/use-cases/call-answering",
      "/use-cases/customer-support",
    ],
    keywords: [
      "AI receptionist for dental",
      "dental office answering service",
      "AI phone agent dentist",
    ],
  },
  {
    slug: "legal",
    name: "Legal",
    shortName: "law firms",
    navLabel: "Legal",
    title: "AI Receptionist for Law Firms",
    description:
      "AI receptionist for law firms that answers intake calls, qualifies new matters, books consults, and escalates existing-client needs to the right desk.",
    h1: "AI Receptionist for Law Firms",
    eyebrow: "Legal practices",
    supporting:
      "Missed intake calls are missed retainers. Call & Flow greets potential clients, runs your qualification questions, and books consultations without giving legal advice.",
    problems: [
      {
        title: "Intake is feast or famine",
        body: "Marketing drives spikes. When attorneys are in court or meetings, new matters hit voicemail.",
      },
      {
        title: "Unqualified consults waste billable time",
        body: "Not every caller is a fit. Consistent screening questions protect attorney calendars.",
      },
      {
        title: "Existing clients need routing",
        body: "Current matters should reach the right paralegal or attorney — not bounce around the firm.",
      },
    ],
    scenarios: [
      {
        title: "New matter intake",
        body: "Potential client describes an issue. The agent collects conflict-check basics you allow and books a consult.",
      },
      {
        title: "Existing client callback",
        body: "Caller has a case number or attorney name. The request is routed or messaged to the right desk.",
      },
      {
        title: "After-hours urgency",
        body: "Arrest, injury, or filing deadline language triggers your escalation path.",
      },
    ],
    workflows: [
      {
        title: "Matter intake questionnaire",
        body: "Ask the screening questions your practice area requires before a human consult.",
      },
      {
        title: "Consult booking",
        body: "Offer consult slots that match attorney availability rules.",
      },
      {
        title: "Conflict and fit filters",
        body: "Capture opposing parties or matter type fields you configure — without giving legal advice.",
      },
      {
        title: "Practice-area routing",
        body: "Send family, PI, business, or criminal inquiries to the correct intake owner.",
      },
      {
        title: "Knowledge FAQs",
        body: "Office hours, directions, and process overviews from approved content only.",
      },
      {
        title: "Human escalation",
        body: "Urgent or privileged conversations move to staff with a clean summary.",
      },
    ],
    benefits: [
      {
        title: "Higher intake capture",
        body: "Potential clients get an immediate professional response.",
      },
      {
        title: "Better-qualified consults",
        body: "Attorneys walk into meetings knowing the basics.",
      },
      {
        title: "Clear ethical boundary",
        body: "Automation handles logistics; legal advice stays with licensed humans.",
      },
    ],
    faqs: [
      {
        question: "Does the AI give legal advice?",
        answer:
          "No. Call & Flow must not provide legal advice. It handles intake logistics, FAQs you approve, and routing to attorneys or staff.",
      },
      {
        question: "Can it support multiple practice areas?",
        answer:
          "Yes. Use branching questions and routing rules so PI, family, and business callers reach the right intake path.",
      },
      {
        question: "Is it useful for solo attorneys?",
        answer:
          "Especially. Solo and small firms often miss calls while in court — an AI receptionist keeps intake moving.",
      },
    ],
    relatedSlugs: ["insurance", "real-estate", "call-centers", "healthcare"],
    useCaseHrefs: [
      "/use-cases/lead-qualification",
      "/use-cases/appointment-booking",
      "/use-cases/call-answering",
    ],
    keywords: [
      "AI receptionist for law firms",
      "legal intake AI",
      "AI phone agent attorneys",
    ],
  },
  {
    slug: "real-estate",
    name: "Real Estate",
    shortName: "real estate teams",
    navLabel: "Real Estate",
    title: "AI Receptionist for Real Estate Teams",
    description:
      "AI receptionist for real estate that qualifies buyer and seller leads, books showings, answers listing FAQs, and keeps agents focused on closings.",
    h1: "AI Receptionist for Real Estate Teams",
    eyebrow: "Real estate",
    supporting:
      "Speed-to-lead wins listings and buyer appointments. Call & Flow answers new inquiries, books showings, and captures seller details while agents are in the field.",
    problems: [
      {
        title: "Portal leads go cold fast",
        body: "Buyers who call a listing expect a same-day reply. Delayed callbacks kill conversion.",
      },
      {
        title: "Agents cannot live on the phone",
        body: "Showing tours and closings conflict with inbound lead calls all day.",
      },
      {
        title: "Seller inquiries need structure",
        body: "Listing presentations go better when address, timeline, and motivation are captured upfront.",
      },
    ],
    scenarios: [
      {
        title: "Listing inquiry",
        body: "Buyer asks about a property. The agent answers approved listing FAQs and offers a showing time.",
      },
      {
        title: "Seller valuation lead",
        body: "Homeowner wants a market check. Contact info, address, and timeline are captured for the listing agent.",
      },
      {
        title: "Open-house follow-up call",
        body: "Caller visited over the weekend. Interest level and preferred callback are logged.",
      },
    ],
    workflows: [
      {
        title: "Lead qualification",
        body: "Ask buyer/seller intent, timeline, and financing status as you define them.",
      },
      {
        title: "Showing booking",
        body: "Offer available windows and confirm contact details for the listing.",
      },
      {
        title: "Listing FAQ answers",
        body: "Share only details you publish — never invent HOA fees or square footage.",
      },
      {
        title: "Agent routing",
        body: "Send hot leads to the on-duty agent or ISA with a summary.",
      },
      {
        title: "After-hours coverage",
        body: "Night and weekend portal calls still get a live conversational response.",
      },
      {
        title: "Team / brokerage scale",
        body: "Support multiple agents or teams with isolated numbers and knowledge where needed.",
      },
    ],
    benefits: [
      {
        title: "Faster speed-to-lead",
        body: "Every inquiry gets an immediate professional conversation.",
      },
      {
        title: "More booked showings",
        body: "Interest turns into calendar events instead of “I’ll have my agent call you.”",
      },
      {
        title: "Cleaner CRM notes",
        body: "Structured intake means less re-qualification later.",
      },
    ],
    faqs: [
      {
        question: "Can AI book property showings?",
        answer:
          "Yes, when showing availability rules are configured. The agent confirms caller details and preferred times.",
      },
      {
        question: "Will it invent listing details?",
        answer:
          "No. Answers come from your knowledge base and approved scripts. Unknown details become a follow-up for the agent.",
      },
      {
        question: "Does this replace an ISA?",
        answer:
          "It covers first-response answering and booking so inside sales agents can focus on nurturing and appointments that need a human touch.",
      },
    ],
    relatedSlugs: ["insurance", "legal", "home-services", "restaurants"],
    useCaseHrefs: [
      "/use-cases/lead-qualification",
      "/use-cases/appointment-booking",
      "/use-cases/sales-calls",
    ],
    keywords: [
      "AI receptionist for real estate",
      "real estate AI phone agent",
      "AI showing booking",
    ],
  },
  {
    slug: "restaurants",
    name: "Restaurants",
    shortName: "restaurants",
    navLabel: "Restaurants",
    title: "AI Receptionist for Restaurants",
    description:
      "AI receptionist for restaurants that answers hours and reservation questions, captures takeout details you allow, and keeps hosts focused on guests in the dining room.",
    h1: "AI Receptionist for Restaurants",
    eyebrow: "Restaurants & hospitality",
    supporting:
      "During service, nobody should abandon a table to answer “are you open on Sundays?” Call & Flow handles hours, directions, and reservation requests so the floor stays calm.",
    problems: [
      {
        title: "Phones vs. hospitality",
        body: "Hosts cannot give great in-person service while fielding repetitive phone questions.",
      },
      {
        title: "Peak-time missed calls",
        body: "Friday night rings that go unanswered are lost covers and frustrated regulars.",
      },
      {
        title: "Simple questions dominate the line",
        body: "Hours, parking, dietary FAQ links, and waitlist status eat time better spent on guests.",
      },
    ],
    scenarios: [
      {
        title: "Hours and directions",
        body: "Caller asks about brunch hours and parking. Answers come from your knowledge base instantly.",
      },
      {
        title: "Reservation request",
        body: "Party size, time, and name are captured and booked according to your reservation rules.",
      },
      {
        title: "Large party / private dining",
        body: "Event inquiry is qualified and routed to a manager with details attached.",
      },
    ],
    workflows: [
      {
        title: "Always-on FAQ answering",
        body: "Hours, location, and house policies without pulling a host off the door.",
      },
      {
        title: "Reservation support",
        body: "Book or request tables based on the flows you enable.",
      },
      {
        title: "Event lead capture",
        body: "Private dining and catering inquiries become structured leads.",
      },
      {
        title: "Multi-location routing",
        body: "Send callers to the right restaurant when you operate several venues.",
      },
      {
        title: "Manager escalation",
        body: "Complaints and special requests transfer to a human with context.",
      },
      {
        title: "Off-peak coverage",
        body: "Answer morning and late-night questions before staff arrive.",
      },
    ],
    benefits: [
      {
        title: "Protect the guest experience",
        body: "Floor staff stay present with diners instead of living on the phone.",
      },
      {
        title: "Capture more reservations",
        body: "Callers reach a helpful voice during the rush.",
      },
      {
        title: "Cleaner event pipeline",
        body: "Catering and private dining leads stop disappearing into sticky notes.",
      },
    ],
    faqs: [
      {
        question: "Can AI take restaurant reservations?",
        answer:
          "Yes when reservation booking is configured. Otherwise it can capture requests and notify your team.",
      },
      {
        question: "Can it handle online ordering questions?",
        answer:
          "It can point callers to the ordering channels and policies you document. It should not invent menu prices.",
      },
      {
        question: "Will guests dislike talking to AI?",
        answer:
          "Most callers want a fast, accurate answer. Keep the tone on-brand and offer a human transfer for special occasions or complaints.",
      },
    ],
    relatedSlugs: ["real-estate", "call-centers", "home-services"],
    useCaseHrefs: [
      "/use-cases/call-answering",
      "/use-cases/appointment-booking",
      "/use-cases/customer-support",
    ],
    keywords: [
      "AI receptionist for restaurants",
      "restaurant phone answering AI",
      "AI reservation phone agent",
    ],
  },
  {
    slug: "insurance",
    name: "Insurance",
    shortName: "insurance agencies",
    navLabel: "Insurance",
    title: "AI Receptionist for Insurance Agencies",
    description:
      "AI receptionist for insurance agencies that qualifies new policy leads, answers service FAQs, and routes claims or urgent client needs to licensed staff.",
    h1: "AI Receptionist for Insurance Agencies",
    eyebrow: "Insurance agencies",
    supporting:
      "New business and service calls compete for the same line. Call & Flow qualifies quote requests, answers routine policy questions you approve, and escalates claims to humans.",
    problems: [
      {
        title: "Quote requests stall in voicemail",
        body: "Shoppers calling for auto or home quotes often move on if nobody answers promptly.",
      },
      {
        title: "Service calls interrupt producers",
        body: "Certificate requests and billing questions pull agents away from selling.",
      },
      {
        title: "Claims need careful routing",
        body: "Upset clients after an accident need a person — but first-response intake can still be structured.",
      },
    ],
    scenarios: [
      {
        title: "New auto quote",
        body: "Caller wants a quote. Drivers, vehicles, and contact details are captured for a licensed agent.",
      },
      {
        title: "Certificate of insurance request",
        body: "Commercial client needs a COI. The request is logged and routed to service staff.",
      },
      {
        title: "Claim first notice",
        body: "Client reports an incident. The agent gathers basics and escalates to the claims desk — without adjusting the claim.",
      },
    ],
    workflows: [
      {
        title: "Quote lead qualification",
        body: "Collect the fields producers need before the first consult.",
      },
      {
        title: "Service request intake",
        body: "COIs, billing questions, and policy change requests become structured tickets.",
      },
      {
        title: "Claims escalation",
        body: "Urgent loss reports move to licensed humans quickly with a summary.",
      },
      {
        title: "Approved FAQ answers",
        body: "Office hours, document upload instructions, and process overviews you publish.",
      },
      {
        title: "Producer routing",
        body: "Send personal vs commercial lines to the right book of business owner.",
      },
      {
        title: "After-hours capture",
        body: "Overnight claim and quote calls are not lost.",
      },
    ],
    benefits: [
      {
        title: "More quote conversations kept",
        body: "Speed-to-lead improves without hiring another CSR overnight.",
      },
      {
        title: "Producers stay in sales mode",
        body: "Routine service intake is handled before a human is needed.",
      },
      {
        title: "Compliant boundaries",
        body: "No invented coverage advice — licensed humans handle advice and binding.",
      },
    ],
    faqs: [
      {
        question: "Can AI bind coverage or give insurance advice?",
        answer:
          "No. Call & Flow should not bind policies or invent coverage interpretations. Licensed staff handle advice; the AI handles intake and routing.",
      },
      {
        question: "Can it help with FNOL?",
        answer:
          "It can collect first-notice details you approve and escalate immediately. Claim decisions stay with your claims process.",
      },
      {
        question: "Does it work for independent agencies?",
        answer:
          "Yes. Small and mid-size agencies often need after-hours coverage and consistent lead capture across multiple carriers’ questions.",
      },
    ],
    relatedSlugs: ["legal", "real-estate", "healthcare", "call-centers"],
    useCaseHrefs: [
      "/use-cases/lead-qualification",
      "/use-cases/customer-support",
      "/use-cases/call-answering",
    ],
    keywords: [
      "AI receptionist for insurance",
      "insurance agency phone AI",
      "AI voice agent insurance leads",
    ],
  },
  {
    slug: "home-services",
    name: "Home Services",
    shortName: "home service businesses",
    navLabel: "Home Services",
    title: "AI Receptionist for Home Services",
    description:
      "AI receptionist for home service businesses that answers calls, books jobs, qualifies leads, and covers after-hours demand across trades.",
    h1: "AI Receptionist for Home Service Businesses",
    eyebrow: "Home & field services",
    supporting:
      "Whether you run one trade or a multi-service brand, missed calls are missed jobs. Call & Flow answers, books, and qualifies so your field teams keep rolling.",
    problems: [
      {
        title: "Phones compete with the field",
        body: "Owners and CSRs bounce between trucks, parts runs, and inbound calls — and something drops.",
      },
      {
        title: "Lead sources are noisy",
        body: "Google, Google Local Services, and referrals all hit the same line with different intent.",
      },
      {
        title: "After-hours is unpaid marketing waste",
        body: "You pay for ads that ring at 9pm into voicemail. Competitors who answer win the job.",
      },
    ],
    scenarios: [
      {
        title: "Same-day service request",
        body: "Caller needs help today. Urgency, address, and issue type are captured for dispatch.",
      },
      {
        title: "Estimate booking",
        body: "Remodel or larger job inquiry becomes a scheduled estimate with contact details.",
      },
      {
        title: "Membership / maintenance customer",
        body: "Existing customer books a routine visit without waiting on hold.",
      },
    ],
    workflows: [
      {
        title: "Unified call answering",
        body: "One professional front door for every marketing number you run.",
      },
      {
        title: "Job qualification",
        body: "Service type, urgency, and service area before a tech is assigned.",
      },
      {
        title: "Appointment booking",
        body: "Book diagnostics and installs into real capacity.",
      },
      {
        title: "Dispatch-friendly notes",
        body: "Structured details your ops board can act on immediately.",
      },
      {
        title: "After-hours revenue capture",
        body: "Turn night calls into next-day booked work.",
      },
      {
        title: "Human escalation",
        body: "VIP customers and complex jobs reach a person with full context.",
      },
    ],
    benefits: [
      {
        title: "Higher booked-job rate",
        body: "More conversations complete with a scheduled next step.",
      },
      {
        title: "Cleaner ops handoff",
        body: "Less re-work asking callers the same questions twice.",
      },
      {
        title: "Scales with marketing spend",
        body: "When ad volume rises, answering capacity rises with it.",
      },
    ],
    faqs: [
      {
        question: "Is this only for HVAC and plumbing?",
        answer:
          "No. Home services covers general contractors, pest control, cleaning, landscaping, garage door, and other field trades that book jobs by phone.",
      },
      {
        question: "Can it work with dispatch tools?",
        answer:
          "Growth and Pro plans include dispatch-oriented workflows in Call & Flow. Integrations depend on your workspace configuration.",
      },
      {
        question: "Can I use different scripts per trade?",
        answer:
          "Yes. Use separate agents or knowledge sets when HVAC, plumbing, and electrical intake differ.",
      },
    ],
    relatedSlugs: ["hvac", "plumbing", "roofing", "electricians"],
    useCaseHrefs: [
      "/use-cases/call-answering",
      "/use-cases/appointment-booking",
      "/use-cases/lead-qualification",
    ],
    keywords: [
      "AI receptionist for home services",
      "home service answering service",
      "AI phone agent field service",
    ],
  },
  {
    slug: "call-centers",
    name: "Call Centers",
    shortName: "call centers",
    navLabel: "Call Centers",
    title: "AI Voice Agents for Call Centers",
    description:
      "AI voice agents for call centers that automate FAQ overflow, qualify inbound intent, and hand off complex calls to live agents with full context.",
    h1: "AI Voice Agents for Call Centers",
    eyebrow: "Call centers & BPOs",
    supporting:
      "Not every call needs a live agent on minute one. Call & Flow automates high-volume FAQs and overflow, then escalates with a summary so your people handle the work that matters.",
    problems: [
      {
        title: "Queue times destroy CSAT",
        body: "When volume spikes, average speed of answer collapses and abandon rates climb.",
      },
      {
        title: "Agents repeat the same answers",
        body: "Hours, status checks, and policy FAQs burn expensive human time.",
      },
      {
        title: "Overflow staffing is expensive",
        body: "Hiring for peaks means idle time in valleys. Automation absorbs the repetitive layer.",
      },
    ],
    scenarios: [
      {
        title: "FAQ containment",
        body: "Caller asks a documented question. The AI resolves it from the knowledge base without a live seat.",
      },
      {
        title: "Intent-based routing",
        body: "Sales, support, and billing intents are identified before a human joins.",
      },
      {
        title: "Overflow during campaigns",
        body: "Marketing-driven spikes are absorbed without catastrophic hold times.",
      },
    ],
    workflows: [
      {
        title: "Automated front-end answering",
        body: "Greet, authenticate lightly as allowed, and identify intent before queueing.",
      },
      {
        title: "Knowledge-grounded support",
        body: "Contain repetitive questions with approved answers.",
      },
      {
        title: "Warm handoff with context",
        body: "Live agents receive summaries instead of making callers repeat themselves.",
      },
      {
        title: "Supervisor visibility",
        body: "Monitor outcomes from the operations console alongside human queues.",
      },
      {
        title: "Multi-tenant / multi-client ops",
        body: "Agencies and BPOs can isolate client numbers, knowledge, and branding.",
      },
      {
        title: "After-hours coverage",
        body: "Keep answering when the floor is closed or thinly staffed.",
      },
    ],
    benefits: [
      {
        title: "Lower cost to serve on repetitive calls",
        body: "Humans focus on exceptions, sales, and retention.",
      },
      {
        title: "More stable service levels",
        body: "Automation cushions volume spikes.",
      },
      {
        title: "Cleaner transfers",
        body: "Context-rich handoffs reduce handle time on the human side.",
      },
    ],
    faqs: [
      {
        question: "Can Call & Flow sit in front of our existing ACD?",
        answer:
          "Deployment patterns vary. Many teams start by pointing overflow or after-hours numbers at Call & Flow, then expand containment over time.",
      },
      {
        question: "Does it support concurrent calls?",
        answer:
          "Yes. Plans include concurrent call limits — see pricing for Starter, Growth, Pro, and Enterprise options.",
      },
      {
        question: "Can supervisors review AI conversations?",
        answer:
          "Yes. Call history and summaries are available in the operations console for coaching and QA workflows you define.",
      },
    ],
    relatedSlugs: ["insurance", "healthcare", "home-services", "legal"],
    useCaseHrefs: [
      "/use-cases/customer-support",
      "/use-cases/call-answering",
      "/use-cases/sales-calls",
    ],
    keywords: [
      "AI voice agents for call centers",
      "call center AI automation",
      "AI phone agents overflow",
    ],
  },
] as const;

export function getIndustry(slug: string): IndustryPage | undefined {
  return industryPages.find((page) => page.slug === slug);
}

export function getIndustrySlugs(): string[] {
  return industryPages.map((page) => page.slug);
}
