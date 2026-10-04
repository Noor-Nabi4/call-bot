/** Alternating storytelling sections for industry and use-case landers. */

import type { FlowStep } from "@/lib/marketing/visuals";

export type StorySection = {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  bullets: readonly string[];
  badge?: string;
  cta?: { href: string; label: string };
  tone?: "bg" | "surface" | "elevated";
  flow: {
    title: string;
    alt: string;
    steps: readonly FlowStep[];
  };
};

export type StoryPageContent = {
  introTitle: string;
  introBody: string;
  sections: readonly StorySection[];
  howTitle: string;
  howSupporting: string;
};

export const industryStories: Record<string, StoryPageContent> = {
  hvac: {
    introTitle: "HVAC companies lose jobs when the phone goes unanswered",
    introBody:
      "Peak-season no-cool calls and overnight furnace failures do not wait for your CSR to finish another line. Call & Flow gives HVAC teams an AI receptionist that answers, qualifies, books, and escalates with the language your callers already use.",
    howTitle: "How Call & Flow works for HVAC companies",
    howSupporting:
      "Start from a home-services template, tune emergency rules and booking windows, then connect the numbers your customers already dial.",
    sections: [
      {
        id: "never-miss-a-lead",
        eyebrow: "Never miss a lead",
        title: "Turn every HVAC call into a booked service",
        description:
          "Call & Flow answers incoming calls, understands the customer’s issue, captures their information, and helps schedule the next step — even when your techs are already on the road.",
        bullets: [
          "Answer calls 24/7, including nights and weekends",
          "Capture name, phone, address, and system details",
          "Identify repair, install, and maintenance requests",
          "Book appointments into real availability",
          "Escalate urgent calls when transfer is available",
        ],
        badge: "Service intake",
        tone: "surface",
        cta: { href: "/use-cases/appointment-booking", label: "See appointment booking" },
        flow: {
          title: "HVAC intake",
          alt: "Flow from HVAC service call through AI receptionist to booked technician appointment",
          steps: [
            { label: "Service call", detail: "No cool / no heat" },
            { label: "AI receptionist", detail: "Captures urgency", tone: "accent" },
            { label: "Qualify request", detail: "System · access notes" },
            { label: "Book tech", detail: "Next open window", tone: "success" },
          ],
        },
      },
      {
        id: "emergency-handling",
        eyebrow: "Smart call handling",
        title: "Handle emergency HVAC calls intelligently",
        description:
          "Not every after-hours ring needs an on-call tech — but some do. Configure the urgency language and routing rules that match how your dispatch board already works.",
        bullets: [
          "Detect urgent language like no heat or gas concerns",
          "Follow your emergency vs standard playbook",
          "Transfer to on-call when a human is required",
          "Keep the caller informed with a clear next step",
        ],
        tone: "bg",
        flow: {
          title: "Urgency routing",
          alt: "Flow showing AI detecting an urgent HVAC request and escalating to on-call staff",
          steps: [
            { label: "Urgent symptoms", detail: "Caller describes emergency" },
            { label: "Rule match", detail: "Your escalation criteria", tone: "accent" },
            { label: "Priority path", detail: "Book or transfer", tone: "success" },
            { label: "Team alert", detail: "Summary attached", tone: "muted" },
          ],
        },
      },
      {
        id: "automated-booking",
        eyebrow: "Automated booking",
        title: "Turn phone calls into scheduled HVAC jobs",
        description:
          "Let homeowners reach your business without waiting for someone to answer every estimate and maintenance call manually.",
        bullets: [
          "Collect job information during the conversation",
          "Offer real diagnostic and install slots",
          "Confirm details before saving the visit",
          "Hand structured notes to dispatch",
        ],
        tone: "surface",
        cta: { href: "/pricing", label: "View pricing" },
        flow: {
          title: "Booking path",
          alt: "Flow from HVAC caller through availability check to confirmed appointment",
          steps: [
            { label: "Caller ready", detail: "Wants a time today" },
            { label: "Availability", detail: "Rules-based slots", tone: "accent" },
            { label: "Confirm details", detail: "Address · contact" },
            { label: "Appointment saved", detail: "Ops can trust it", tone: "success" },
          ],
        },
      },
      {
        id: "human-handoff",
        eyebrow: "Human handoff",
        title: "AI handles the routine. Your team handles what matters.",
        description:
          "Warranty disputes, complex installs, and VIP accounts still need people. When a caller needs a human, Call & Flow can hand off with context instead of a cold transfer.",
        bullets: [
          "Intelligent routing to the right desk",
          "Human escalation with call summary",
          "Context preserved for the next person",
          "Fewer leads lost to voicemail",
        ],
        tone: "elevated",
        flow: {
          title: "Handoff",
          alt: "Flow showing HVAC AI receptionist transferring a complex call to a human with context",
          steps: [
            { label: "Complex request", detail: "Needs a person" },
            { label: "AI summary", detail: "Issue already captured", tone: "accent" },
            { label: "Transfer / callback", detail: "Per your rules", tone: "success" },
            { label: "Human continues", detail: "No repeated questions", tone: "muted" },
          ],
        },
      },
    ],
  },
  plumbing: {
    introTitle: "Plumbing emergencies and routine jobs compete for the same line",
    introBody:
      "Active leaks, clogged drains, and water-heater quotes all hit your phone — often after hours. Call & Flow answers with plumbing-aware intake so urgent work is triaged and standard jobs still get booked.",
    howTitle: "How Call & Flow works for plumbing companies",
    howSupporting:
      "Configure leak vs standard service language, service-area checks, and booking rules that match how your trucks already roll.",
    sections: [
      {
        id: "answer-every-call",
        eyebrow: "Always-on answering",
        title: "Never send a leak call to voicemail",
        description:
          "When water is running, callers hang up fast. An AI receptionist captures the address, severity, and contact details on the first ring.",
        bullets: [
          "Answer leak and clog calls immediately",
          "Capture address and shutoff details when shared",
          "Separate emergency from standard requests",
          "Book service windows your office trusts",
        ],
        tone: "surface",
        flow: {
          title: "Leak intake",
          alt: "Plumbing leak call handled by AI receptionist through triage and booking",
          steps: [
            { label: "Leak call", detail: "Water damage risk" },
            { label: "AI receptionist", detail: "Triage severity", tone: "accent" },
            { label: "Service area", detail: "Coverage confirmed" },
            { label: "Book truck", detail: "Priority window", tone: "success" },
          ],
        },
      },
      {
        id: "emergency-triage",
        eyebrow: "Emergency triage",
        title: "Tell true emergencies from routine plumbing work",
        description:
          "Flooding and sewage backup need a different path than a slow drain. Your rules decide what escalates and what books for the next day.",
        bullets: [
          "Flag active flooding and no-water scenarios",
          "Apply after-hours emergency playbooks",
          "Route commercial vs residential when configured",
          "Escalate to a person with a clean summary",
        ],
        tone: "bg",
        flow: {
          title: "Triage rules",
          alt: "AI plumbing receptionist applying emergency rules before dispatch",
          steps: [
            { label: "Caller symptoms", detail: "Leak · clog · no water" },
            { label: "Rule engine", detail: "Your urgency criteria", tone: "accent" },
            { label: "Emergency path", detail: "Escalate or rush book", tone: "success" },
            { label: "Standard path", detail: "Next available slot", tone: "muted" },
          ],
        },
      },
      {
        id: "quote-capture",
        eyebrow: "Replacement leads",
        title: "Turn water-heater and repipe calls into structured leads",
        description:
          "Bigger plumbing jobs need more than a sticky note. Capture preference, timeline, and contact details for sales follow-up.",
        bullets: [
          "Qualify tank vs tankless interest",
          "Collect preferred visit windows",
          "Save lead notes for estimators",
          "Book consults when capacity allows",
        ],
        tone: "surface",
        cta: { href: "/use-cases/lead-qualification", label: "See lead qualification" },
        flow: {
          title: "Estimate lead",
          alt: "Plumbing estimate inquiry captured and routed by AI receptionist",
          steps: [
            { label: "Quote request", detail: "Water heater / repipe" },
            { label: "Discovery", detail: "Configured questions", tone: "accent" },
            { label: "Lead saved", detail: "Contact + notes", tone: "success" },
            { label: "Sales follow-up", detail: "Human closes", tone: "muted" },
          ],
        },
      },
      {
        id: "after-hours",
        eyebrow: "After-hours coverage",
        title: "Keep overnight plumbing demand from disappearing",
        description:
          "Night and weekend callers still expect help. Book morning capacity or reach on-call staff according to the rules you set.",
        bullets: [
          "Cover nights without a full CSR shift",
          "Book first-available morning slots",
          "Transfer when on-call is available",
          "Preserve context for the next human",
        ],
        tone: "elevated",
        flow: {
          title: "After hours",
          alt: "After-hours plumbing call answered, booked, or escalated by AI",
          steps: [
            { label: "Night call", detail: "Office closed" },
            { label: "AI answers", detail: "Brand greeting", tone: "accent" },
            { label: "Book or escalate", detail: "Per playbook", tone: "success" },
            { label: "Morning ready", detail: "Dispatch has notes", tone: "muted" },
          ],
        },
      },
    ],
  },
  roofing: {
    introTitle: "Storm spikes and retail reroof leads need the same fast answer",
    introBody:
      "After hail, inspection requests pile up while estimators are already on roofs. Call & Flow captures storm and retail leads, books inspections, and keeps sales follow-up moving.",
    howTitle: "How Call & Flow works for roofing companies",
    howSupporting:
      "Tune inspection booking, insurance-job questions, and sales handoff so storm demand does not overflow into voicemail.",
    sections: [
      {
        id: "storm-capture",
        eyebrow: "Storm demand",
        title: "Capture inspection requests while homeowners are ready to act",
        description:
          "Speed-to-lead wins insurance work. An AI receptionist answers, qualifies, and books roof assessments before competitors do.",
        bullets: [
          "Answer storm spike volume without temp staff",
          "Capture address and damage details you allow",
          "Book inspection windows at scale",
          "Route hot leads to sales with notes",
        ],
        tone: "surface",
        flow: {
          title: "Storm lead",
          alt: "Roofing storm damage lead captured and inspection booked by AI",
          steps: [
            { label: "Hail inquiry", detail: "Homeowner calls" },
            { label: "AI receptionist", detail: "Qualifies job", tone: "accent" },
            { label: "Book inspection", detail: "Estimator slot", tone: "success" },
            { label: "Sales queue", detail: "CRM-ready notes", tone: "muted" },
          ],
        },
      },
      {
        id: "qualify-jobs",
        eyebrow: "Lead quality",
        title: "Send estimators to better-qualified roofing jobs",
        description:
          "Not every caller is ready for a full replacement. Ask the discovery questions your sales process already depends on.",
        bullets: [
          "Screen retail vs insurance intent",
          "Collect roof age and timeline when configured",
          "Avoid inventing materials or pricing",
          "Hand structured notes to closers",
        ],
        tone: "bg",
        cta: { href: "/use-cases/lead-qualification", label: "Lead qualification" },
        flow: {
          title: "Qualification",
          alt: "Roofing lead qualification questions before estimator visit",
          steps: [
            { label: "Inbound lead", detail: "Inspection or quote" },
            { label: "Discovery", detail: "Your sales questions", tone: "accent" },
            { label: "Fit check", detail: "Ready for site visit" },
            { label: "Estimator", detail: "Arrives prepared", tone: "success" },
          ],
        },
      },
      {
        id: "retail-pipeline",
        eyebrow: "Year-round pipeline",
        title: "Keep retail reroof and leak calls moving outside storm season",
        description:
          "Leak investigations and retail replacements still need reliable phone coverage when marketing is quiet.",
        bullets: [
          "Answer leak and maintenance calls",
          "Book diagnostic visits",
          "Capture non-storm quote requests",
          "Cover after-hours inquiries",
        ],
        tone: "surface",
        flow: {
          title: "Retail path",
          alt: "Retail roofing inquiry booked through AI receptionist",
          steps: [
            { label: "Retail call", detail: "Reroof / leak" },
            { label: "AI intake", detail: "Details captured", tone: "accent" },
            { label: "Book visit", detail: "Open capacity", tone: "success" },
            { label: "Follow-up", detail: "Sales continues", tone: "muted" },
          ],
        },
      },
      {
        id: "sales-handoff",
        eyebrow: "Sales handoff",
        title: "Give closers context, not another cold callback",
        description:
          "When a human should take over, transfer or queue with the conversation summary already attached.",
        bullets: [
          "Warm or cold transfer per your rules",
          "Preserve insurance and property notes",
          "Reduce re-qualification time",
          "Keep campaign ROI from dying in voicemail",
        ],
        tone: "elevated",
        flow: {
          title: "Closer ready",
          alt: "Roofing AI handoff to sales with conversation context",
          steps: [
            { label: "Hot lead", detail: "Ready for human" },
            { label: "Summary", detail: "Intake complete", tone: "accent" },
            { label: "Sales alert", detail: "Rep notified", tone: "success" },
            { label: "Close path", detail: "Human conversation", tone: "muted" },
          ],
        },
      },
    ],
  },
  electricians: {
    introTitle: "Electrical callers need careful intake — and a fast next step",
    introBody:
      "From sparking outlets to EV charger installs, electrical work mixes safety urgency with high-margin project leads. Call & Flow answers professionally, qualifies the job, and escalates safety language per your script.",
    howTitle: "How Call & Flow works for electricians",
    howSupporting:
      "Configure safety escalation, install qualification questions, and booking rules for residential and commercial lines.",
    sections: [
      {
        id: "safety-first",
        eyebrow: "Safety-aware intake",
        title: "Treat burning smells and sparking outlets with urgency",
        description:
          "Electrical emergencies need consistent questions and clear escalation — not a vague promise to call back.",
        bullets: [
          "Flag safety keywords you define",
          "Capture symptoms without inventing advice",
          "Escalate to a licensed team member when needed",
          "Book diagnostics for non-emergency repairs",
        ],
        tone: "surface",
        flow: {
          title: "Safety path",
          alt: "Electrical emergency call triaged and escalated by AI receptionist",
          steps: [
            { label: "Safety call", detail: "Sparking / burning smell" },
            { label: "Scripted triage", detail: "Your criteria", tone: "accent" },
            { label: "Escalate", detail: "Human or priority book", tone: "success" },
            { label: "Context passed", detail: "Tech arrives ready", tone: "muted" },
          ],
        },
      },
      {
        id: "install-leads",
        eyebrow: "Install pipeline",
        title: "Qualify EV charger, panel, and generator leads completely",
        description:
          "High-margin installs need property details before a profitable site visit. Capture them while interest is high.",
        bullets: [
          "Collect vehicle, panel, and site details you allow",
          "Book consults into real availability",
          "Route commercial build-outs separately",
          "Hand estimators structured notes",
        ],
        tone: "bg",
        cta: { href: "/use-cases/lead-qualification", label: "Lead qualification" },
        flow: {
          title: "Install lead",
          alt: "EV charger install lead qualified and booked by AI phone agent",
          steps: [
            { label: "Install inquiry", detail: "EV / panel / generator" },
            { label: "Qualify", detail: "Configured fields", tone: "accent" },
            { label: "Book consult", detail: "Site visit", tone: "success" },
            { label: "Estimator", detail: "Follows up prepared", tone: "muted" },
          ],
        },
      },
      {
        id: "owner-operator",
        eyebrow: "Field coverage",
        title: "Stay on the tools while the phone still gets answered",
        description:
          "Owner-operators should not lose midday leads because they are mid-job. Keep a professional front door on every marketing number.",
        bullets: [
          "Answer while you are on a service call",
          "Book standard troubleshooting visits",
          "Cover after-hours inquiries",
          "Transfer VIP or complex commercial work",
        ],
        tone: "surface",
        flow: {
          title: "Field mode",
          alt: "Electrician phone coverage while technicians are in the field",
          steps: [
            { label: "Busy in field", detail: "Missed rings risk" },
            { label: "AI answers", detail: "Brand voice", tone: "accent" },
            { label: "Book or message", detail: "Next step set", tone: "success" },
            { label: "You focus", detail: "Work continues", tone: "muted" },
          ],
        },
      },
      {
        id: "human-escalation",
        eyebrow: "Licensed handoff",
        title: "Keep code and commercial complexity with humans",
        description:
          "AI should not invent electrical advice. Complex code questions and commercial scopes escalate cleanly to your team.",
        bullets: [
          "No invented code or safety advice",
          "Escalate with a conversation summary",
          "Route by residential vs commercial rules",
          "Protect trust on sensitive jobs",
        ],
        tone: "elevated",
        flow: {
          title: "Escalation",
          alt: "Complex electrical inquiry handed to a licensed human with context",
          steps: [
            { label: "Complex ask", detail: "Needs licensed human" },
            { label: "AI pauses", detail: "No invented advice", tone: "accent" },
            { label: "Transfer", detail: "Summary attached", tone: "success" },
            { label: "Electrician", detail: "Continues call", tone: "muted" },
          ],
        },
      },
    ],
  },
  healthcare: {
    introTitle: "Clinic phones compete with the patients already in the lobby",
    introBody:
      "Front desks juggle check-in, insurance questions, and scheduling. Call & Flow covers routine phone work for hours and booking — without inventing clinical advice.",
    howTitle: "How Call & Flow works for healthcare clinics",
    howSupporting:
      "Use non-clinical FAQ knowledge, scheduling rules, and escalation scripts your practice approves.",
    sections: [
      {
        id: "front-desk-coverage",
        eyebrow: "Front-desk coverage",
        title: "Answer patient calls without abandoning the lobby",
        description:
          "Reduce hold times for hours, location, and scheduling questions so staff can stay with in-clinic patients.",
        bullets: [
          "Answer routine scheduling and FAQ calls",
          "Share only approved operational information",
          "Book visits according to your rules",
          "Escalate urgent symptom scripts carefully",
        ],
        tone: "surface",
        flow: {
          title: "Clinic intake",
          alt: "Healthcare clinic call answered and scheduled by AI receptionist",
          steps: [
            { label: "Patient call", detail: "Hours or scheduling" },
            { label: "AI receptionist", detail: "Non-clinical help", tone: "accent" },
            { label: "Book or answer", detail: "Approved knowledge", tone: "success" },
            { label: "Staff escalate", detail: "When required", tone: "muted" },
          ],
        },
      },
      {
        id: "scheduling",
        eyebrow: "Appointment support",
        title: "Help patients book without endless hold music",
        description:
          "Offer availability based on rules you control and confirm the details that matter before saving the visit.",
        bullets: [
          "Support new and existing patient flows you configure",
          "Confirm contact and visit reason fields you allow",
          "Avoid inventing clinical guidance",
          "Open follow-ups when booking is not possible",
        ],
        tone: "bg",
        cta: { href: "/use-cases/appointment-booking", label: "Appointment booking" },
        flow: {
          title: "Scheduling",
          alt: "Patient appointment booking flow with AI receptionist",
          steps: [
            { label: "Schedule request", detail: "Caller wants a visit" },
            { label: "Availability", detail: "Clinic rules", tone: "accent" },
            { label: "Confirm details", detail: "Required fields" },
            { label: "Visit saved", detail: "Trusted booking", tone: "success" },
          ],
        },
      },
      {
        id: "policy-safe",
        eyebrow: "Policy-safe automation",
        title: "Automate phones without playing doctor",
        description:
          "Call & Flow is business phone automation — not a medical device. Urgent scenarios follow scripts you approve.",
        bullets: [
          "No invented diagnoses",
          "Escalation scripts for urgent symptoms",
          "Knowledge limited to approved documents",
          "Humans handle clinical conversations",
        ],
        tone: "surface",
        flow: {
          title: "Guardrails",
          alt: "Healthcare AI receptionist escalating clinical concerns to staff",
          steps: [
            { label: "Sensitive ask", detail: "Clinical concern" },
            { label: "Safe response", detail: "Scripted path", tone: "accent" },
            { label: "Escalate", detail: "Nurse / staff line", tone: "success" },
            { label: "Human care", detail: "Clinical judgment", tone: "muted" },
          ],
        },
      },
      {
        id: "multi-location",
        eyebrow: "Multi-location",
        title: "Route callers to the right clinic or department",
        description:
          "When you run multiple locations or departments, use numbers and routing rules that keep intake clean.",
        bullets: [
          "Separate knowledge per location when needed",
          "Route by department or number",
          "Cover after-hours messaging consistently",
          "Keep each clinic’s data isolated in multi-tenant ops",
        ],
        tone: "elevated",
        flow: {
          title: "Routing",
          alt: "Multi-location healthcare call routing with AI receptionist",
          steps: [
            { label: "Caller", detail: "Which location?" },
            { label: "Route", detail: "Number / intent rules", tone: "accent" },
            { label: "Local knowledge", detail: "Hours · parking" },
            { label: "Book locally", detail: "Correct clinic", tone: "success" },
          ],
        },
      },
    ],
  },
  dental: {
    introTitle: "Empty chairs often start as unanswered phones",
    introBody:
      "New-patient shoppers and hygiene rebooks hang up when the front desk is mid-check-in. Call & Flow books visits, answers approved FAQs, and covers lunch and after-hours gaps.",
    howTitle: "How Call & Flow works for dental practices",
    howSupporting:
      "Configure hygiene and new-patient booking flows, approved insurance FAQs, and tooth-pain escalation scripts.",
    sections: [
      {
        id: "fill-schedule",
        eyebrow: "Fill the schedule",
        title: "Book cleanings and exams while staff stay chairside",
        description:
          "Keep the hygiene column full by letting an AI receptionist offer real open times and confirm patient details.",
        bullets: [
          "Book hygiene and exam visits",
          "Capture new-patient basics",
          "Answer hours and parking FAQs you publish",
          "Reduce voicemail for shoppers comparing offices",
        ],
        tone: "surface",
        cta: { href: "/use-cases/appointment-booking", label: "Appointment booking" },
        flow: {
          title: "Hygiene booking",
          alt: "Dental cleaning appointment booked by AI receptionist",
          steps: [
            { label: "Patient call", detail: "Wants a cleaning" },
            { label: "AI receptionist", detail: "Offers open times", tone: "accent" },
            { label: "Confirm details", detail: "Name · preference" },
            { label: "Chair booked", detail: "Schedule updated", tone: "success" },
          ],
        },
      },
      {
        id: "new-patients",
        eyebrow: "New patients",
        title: "Make the first call feel organized and welcoming",
        description:
          "First impressions start on the phone. Collect the details your front desk needs without inventing clinical advice.",
        bullets: [
          "Capture reason for visit and preferred times",
          "Share approved insurance process info only",
          "Book first available new-patient slots",
          "Escalate treatment-plan questions to staff",
        ],
        tone: "bg",
        flow: {
          title: "New patient",
          alt: "New dental patient intake and booking with AI receptionist",
          steps: [
            { label: "New caller", detail: "Shopping for a dentist" },
            { label: "Intake", detail: "Configured questions", tone: "accent" },
            { label: "Book exam", detail: "Open capacity", tone: "success" },
            { label: "Front desk", detail: "Completes forms later", tone: "muted" },
          ],
        },
      },
      {
        id: "pain-calls",
        eyebrow: "Urgent dental pain",
        title: "Handle after-hours tooth pain with a clear next step",
        description:
          "Pain calls need empathy and a scripted path — not a diagnosis from automation.",
        bullets: [
          "Follow your emergency or next-day slot rules",
          "Never invent dental advice",
          "Capture callback details overnight",
          "Transfer when a human should join",
        ],
        tone: "surface",
        flow: {
          title: "Pain path",
          alt: "After-hours dental pain call escalated or booked by AI",
          steps: [
            { label: "Pain call", detail: "After hours" },
            { label: "Script", detail: "Approved urgency path", tone: "accent" },
            { label: "Book / escalate", detail: "Next step clear", tone: "success" },
            { label: "Team follows", detail: "Notes waiting", tone: "muted" },
          ],
        },
      },
      {
        id: "calm-front-desk",
        eyebrow: "Calmer front desk",
        title: "Let staff focus on patients in the office",
        description:
          "Routine phone work stops interrupting rooming, check-out, and chairside coordination.",
        bullets: [
          "Deflect repetitive FAQ calls",
          "Keep CTAs for complex billing with humans",
          "Cover lunch-hour rings",
          "Improve the patient phone experience",
        ],
        tone: "elevated",
        flow: {
          title: "Front desk assist",
          alt: "Dental front desk supported by AI call answering",
          steps: [
            { label: "Busy lobby", detail: "Staff with patients" },
            { label: "AI covers line", detail: "Routine calls", tone: "accent" },
            { label: "Book / FAQ", detail: "Resolved", tone: "success" },
            { label: "Humans focus", detail: "In-office care", tone: "muted" },
          ],
        },
      },
    ],
  },
  legal: {
    introTitle: "Missed intake calls are missed retainers",
    introBody:
      "Attorneys cannot live on the phone while in court or meetings. Call & Flow runs your intake questions, books consults, and routes existing-client needs — without giving legal advice.",
    howTitle: "How Call & Flow works for law firms",
    howSupporting:
      "Configure practice-area routing, consult booking, and escalation for urgent matters your firm defines.",
    sections: [
      {
        id: "intake-capture",
        eyebrow: "Intake capture",
        title: "Answer new-matter calls before they hire someone else",
        description:
          "Potential clients expect a professional response now. Capture conflict-check basics you allow and book the consult.",
        bullets: [
          "Greet prospective clients professionally",
          "Run your screening questionnaire",
          "Book attorney consult slots",
          "Never provide legal advice",
        ],
        tone: "surface",
        cta: { href: "/use-cases/lead-qualification", label: "Lead qualification" },
        flow: {
          title: "Matter intake",
          alt: "Law firm intake call qualified and consult booked by AI receptionist",
          steps: [
            { label: "Prospective client", detail: "New matter" },
            { label: "Screening", detail: "Your questions", tone: "accent" },
            { label: "Book consult", detail: "Attorney calendar", tone: "success" },
            { label: "Attorney prep", detail: "Notes ready", tone: "muted" },
          ],
        },
      },
      {
        id: "practice-routing",
        eyebrow: "Practice-area routing",
        title: "Send PI, family, and business callers to the right path",
        description:
          "Different desks need different intake. Branch by practice area so the right owner sees the lead.",
        bullets: [
          "Route by matter type",
          "Capture opposing-party fields you configure",
          "Separate existing-client callbacks",
          "Escalate urgent filing or arrest language",
        ],
        tone: "bg",
        flow: {
          title: "Routing",
          alt: "Legal intake routed by practice area with AI receptionist",
          steps: [
            { label: "Caller intent", detail: "Practice area" },
            { label: "Branch", detail: "PI / family / business", tone: "accent" },
            { label: "Owner queue", detail: "Correct intake desk", tone: "success" },
            { label: "Human review", detail: "Attorney / staff", tone: "muted" },
          ],
        },
      },
      {
        id: "existing-clients",
        eyebrow: "Existing clients",
        title: "Route current matters without bouncing around the firm",
        description:
          "Clients with an attorney name or matter reference should reach the right paralegal or lawyer quickly.",
        bullets: [
          "Capture attorney or case identifiers you allow",
          "Take structured messages when humans are busy",
          "Transfer with context",
          "Protect privileged conversations with human escalation",
        ],
        tone: "surface",
        flow: {
          title: "Client route",
          alt: "Existing legal client call routed to the correct desk",
          steps: [
            { label: "Existing client", detail: "Needs update" },
            { label: "Identify desk", detail: "Attorney / matter", tone: "accent" },
            { label: "Message or transfer", detail: "Per availability", tone: "success" },
            { label: "Staff responds", detail: "With full notes", tone: "muted" },
          ],
        },
      },
      {
        id: "ethical-boundary",
        eyebrow: "Clear boundaries",
        title: "Logistics automation. Legal advice stays human.",
        description:
          "Call & Flow handles intake logistics and approved FAQs. Licensed professionals handle advice and strategy.",
        bullets: [
          "No legal advice from the AI",
          "Approved process FAQs only",
          "Urgent matters escalate immediately",
          "Solo and small firms keep intake moving in court hours",
        ],
        tone: "elevated",
        flow: {
          title: "Boundaries",
          alt: "Legal AI receptionist escalating advice questions to attorneys",
          steps: [
            { label: "Advice question", detail: "Needs attorney" },
            { label: "AI boundary", detail: "No legal advice", tone: "accent" },
            { label: "Escalate", detail: "Licensed human", tone: "success" },
            { label: "Counsel", detail: "Handles merits", tone: "muted" },
          ],
        },
      },
    ],
  },
  "real-estate": {
    introTitle: "Speed-to-lead still decides who gets the showing",
    introBody:
      "Portal calls and listing inquiries go cold in minutes. Call & Flow answers, qualifies buyer and seller intent, and books showings while agents are in the field.",
    howTitle: "How Call & Flow works for real estate teams",
    howSupporting:
      "Use approved listing FAQs, showing availability rules, and agent routing that matches your team or brokerage structure.",
    sections: [
      {
        id: "speed-to-lead",
        eyebrow: "Speed-to-lead",
        title: "Answer listing inquiries before the next agent does",
        description:
          "Buyers who call a sign or portal listing expect a same-day conversation. Keep first response immediate and on-brand.",
        bullets: [
          "Answer portal and sign calls instantly",
          "Share only approved listing details",
          "Capture buyer timeline and contact info",
          "Offer showing windows when configured",
        ],
        tone: "surface",
        flow: {
          title: "Listing call",
          alt: "Real estate listing inquiry answered and showing booked by AI",
          steps: [
            { label: "Listing inquiry", detail: "Buyer calls" },
            { label: "AI receptionist", detail: "Approved FAQs", tone: "accent" },
            { label: "Qualify interest", detail: "Timeline · intent" },
            { label: "Book showing", detail: "Open window", tone: "success" },
          ],
        },
      },
      {
        id: "seller-leads",
        eyebrow: "Seller intake",
        title: "Structure listing presentation leads from the first call",
        description:
          "Seller calls go better when address, timeline, and motivation are captured before the listing agent dials back.",
        bullets: [
          "Capture property address and timeline",
          "Ask motivation questions you define",
          "Route to the listing specialist",
          "Book valuation appointments",
        ],
        tone: "bg",
        cta: { href: "/use-cases/lead-qualification", label: "Lead qualification" },
        flow: {
          title: "Seller lead",
          alt: "Seller valuation lead captured by AI receptionist for listing agent",
          steps: [
            { label: "Seller call", detail: "Wants a market check" },
            { label: "Discovery", detail: "Address · timing", tone: "accent" },
            { label: "Lead saved", detail: "Structured notes", tone: "success" },
            { label: "Listing agent", detail: "Follows up", tone: "muted" },
          ],
        },
      },
      {
        id: "showing-booking",
        eyebrow: "Showings",
        title: "Convert interest into calendar events, not callbacks",
        description:
          "When showing rules are connected, book the visit while motivation is highest.",
        bullets: [
          "Offer available showing times",
          "Confirm contact details",
          "Reduce ‘my agent will call you’ dead ends",
          "Escalate special requests to humans",
        ],
        tone: "surface",
        flow: {
          title: "Showing",
          alt: "Property showing booked through AI voice agent",
          steps: [
            { label: "Interested buyer", detail: "Wants to see it" },
            { label: "Availability", detail: "Showing rules", tone: "accent" },
            { label: "Confirm", detail: "Time · contact" },
            { label: "On calendar", detail: "Agent notified", tone: "success" },
          ],
        },
      },
      {
        id: "agent-focus",
        eyebrow: "Agent focus",
        title: "Keep agents in appointments while AI covers first response",
        description:
          "Touring and closing conflict with inbound rings all day. First response and booking stay covered.",
        bullets: [
          "After-hours and weekend coverage",
          "ISA-style qualification support",
          "Hot-lead transfer when a closer should join",
          "Cleaner CRM notes for the team",
        ],
        tone: "elevated",
        flow: {
          title: "Team coverage",
          alt: "Real estate team covered by AI while agents are in the field",
          steps: [
            { label: "Agent busy", detail: "Showing / closing" },
            { label: "AI covers", detail: "First response", tone: "accent" },
            { label: "Qualify + book", detail: "Next step set", tone: "success" },
            { label: "Agent closes", detail: "Human relationship", tone: "muted" },
          ],
        },
      },
    ],
  },
  restaurants: {
    introTitle: "During service, the phone should not steal the dining room",
    introBody:
      "Hosts cannot abandon guests for hours and reservation questions. Call & Flow answers repetitive calls, supports reservations, and routes events to a manager.",
    howTitle: "How Call & Flow works for restaurants",
    howSupporting:
      "Publish hours and policy knowledge, enable reservation flows you support, and escalate complaints to humans.",
    sections: [
      {
        id: "protect-service",
        eyebrow: "Protect service",
        title: "Keep hosts with guests while AI covers the line",
        description:
          "Friday-night rings about hours, parking, and waitlists should not pull your best people off the door.",
        bullets: [
          "Answer hours and directions instantly",
          "Share approved house policies",
          "Capture reservation requests",
          "Cover off-peak and late-night questions",
        ],
        tone: "surface",
        flow: {
          title: "Service rush",
          alt: "Restaurant phone FAQ and reservation handling during dinner rush",
          steps: [
            { label: "Guest call", detail: "Busy service" },
            { label: "AI answers", detail: "Hours · parking", tone: "accent" },
            { label: "Reserve / inform", detail: "Clear next step", tone: "success" },
            { label: "Floor stays calm", detail: "Hosts with guests", tone: "muted" },
          ],
        },
      },
      {
        id: "reservations",
        eyebrow: "Reservations",
        title: "Turn reservation intent into a held table or clear request",
        description:
          "When reservation booking is configured, capture party size, time, and name — or notify your team when a human must confirm.",
        bullets: [
          "Collect party size and preferred time",
          "Book when your rules allow",
          "Take structured requests otherwise",
          "Escalate large parties and private dining",
        ],
        tone: "bg",
        cta: { href: "/use-cases/appointment-booking", label: "Booking workflows" },
        flow: {
          title: "Reservation",
          alt: "Restaurant reservation request handled by AI receptionist",
          steps: [
            { label: "Reserve please", detail: "Party size · time" },
            { label: "AI collects", detail: "Required fields", tone: "accent" },
            { label: "Book / request", detail: "Per configuration", tone: "success" },
            { label: "Confirm path", detail: "Guest knows next step", tone: "muted" },
          ],
        },
      },
      {
        id: "events",
        eyebrow: "Events & catering",
        title: "Stop private dining leads from vanishing into sticky notes",
        description:
          "Event inquiries need structured capture and a manager follow-up — not a rushed promise mid-service.",
        bullets: [
          "Qualify event date and headcount",
          "Capture contact details cleanly",
          "Route to the events owner",
          "Keep the dining room uninterrupted",
        ],
        tone: "surface",
        flow: {
          title: "Event lead",
          alt: "Restaurant private dining lead captured by AI phone agent",
          steps: [
            { label: "Event inquiry", detail: "Private dining" },
            { label: "Qualify", detail: "Date · headcount", tone: "accent" },
            { label: "Lead saved", detail: "Manager queue", tone: "success" },
            { label: "Human close", detail: "Events follow-up", tone: "muted" },
          ],
        },
      },
      {
        id: "escalation",
        eyebrow: "Manager escalation",
        title: "Complaints and special occasions deserve a person",
        description:
          "Keep the AI great at logistics. Upset guests and VIP moments transfer to a human with context.",
        bullets: [
          "Transfer complaints quickly",
          "Preserve what already happened on the call",
          "Offer a human path for special requests",
          "Protect the brand experience",
        ],
        tone: "elevated",
        flow: {
          title: "Manager path",
          alt: "Restaurant complaint or VIP call transferred to a manager",
          steps: [
            { label: "Sensitive call", detail: "Complaint / VIP" },
            { label: "AI recognizes", detail: "Needs human", tone: "accent" },
            { label: "Transfer", detail: "Summary attached", tone: "success" },
            { label: "Manager", detail: "Owns the moment", tone: "muted" },
          ],
        },
      },
    ],
  },
  insurance: {
    introTitle: "Quote requests and service calls fight for the same producers",
    introBody:
      "Shoppers move on if nobody answers, while COI and billing questions interrupt selling time. Call & Flow qualifies quotes, intakes service requests, and escalates claims to licensed staff.",
    howTitle: "How Call & Flow works for insurance agencies",
    howSupporting:
      "Configure quote fields, service routing, and claims escalation — without letting automation invent coverage advice.",
    sections: [
      {
        id: "quote-speed",
        eyebrow: "Quote velocity",
        title: "Keep inbound quote calls from dying in voicemail",
        description:
          "Capture the fields producers need and route sales-ready conversations to a licensed agent.",
        bullets: [
          "Answer auto and home quote calls quickly",
          "Collect drivers, vehicles, and contact details you allow",
          "Book producer callbacks or transfers",
          "Never bind coverage or invent advice",
        ],
        tone: "surface",
        cta: { href: "/use-cases/lead-qualification", label: "Lead qualification" },
        flow: {
          title: "Quote intake",
          alt: "Insurance quote request qualified and routed to a producer",
          steps: [
            { label: "Quote call", detail: "Shopper ready" },
            { label: "AI collects", detail: "Configured fields", tone: "accent" },
            { label: "Producer route", detail: "Licensed human", tone: "success" },
            { label: "Quote work", detail: "Agent continues", tone: "muted" },
          ],
        },
      },
      {
        id: "service-desk",
        eyebrow: "Service intake",
        title: "Take COI and policy service requests off the producer’s plate",
        description:
          "Routine service work becomes structured tickets so producers stay in sales mode longer.",
        bullets: [
          "Log certificate of insurance requests",
          "Capture billing and policy-change intents",
          "Route to service staff",
          "Answer approved process FAQs",
        ],
        tone: "bg",
        flow: {
          title: "Service ticket",
          alt: "Insurance service request intake by AI receptionist",
          steps: [
            { label: "Service call", detail: "COI / billing" },
            { label: "AI intake", detail: "Structured details", tone: "accent" },
            { label: "Service queue", detail: "Right desk", tone: "success" },
            { label: "Staff completes", detail: "Producer uninterrupted", tone: "muted" },
          ],
        },
      },
      {
        id: "claims-escalation",
        eyebrow: "Claims escalation",
        title: "Get first-notice calls to humans fast — without adjusting the claim",
        description:
          "Upset clients after a loss need people. AI can gather basics you approve and escalate immediately.",
        bullets: [
          "Collect FNOL details you allow",
          "Escalate to claims staff quickly",
          "No claim decisions from automation",
          "Preserve empathy with a clear human path",
        ],
        tone: "surface",
        flow: {
          title: "FNOL path",
          alt: "Insurance first notice of loss escalated to claims staff",
          steps: [
            { label: "Loss reported", detail: "Client needs help" },
            { label: "Basics captured", detail: "Approved fields", tone: "accent" },
            { label: "Escalate now", detail: "Claims desk", tone: "success" },
            { label: "Human handles", detail: "Advice + process", tone: "muted" },
          ],
        },
      },
      {
        id: "compliance-boundary",
        eyebrow: "Licensed boundary",
        title: "Automation for intake. Advice stays licensed.",
        description:
          "Independent agencies can cover after-hours demand without crossing into coverage interpretation.",
        bullets: [
          "No binding or coverage promises from AI",
          "Producer and service routing by line of business",
          "After-hours quote and claim capture",
          "Clean handoff summaries",
        ],
        tone: "elevated",
        flow: {
          title: "Boundaries",
          alt: "Insurance AI receptionist escalating advice to licensed agents",
          steps: [
            { label: "Advice ask", detail: "Coverage question" },
            { label: "AI boundary", detail: "No invented advice", tone: "accent" },
            { label: "Licensed route", detail: "Producer / CSR", tone: "success" },
            { label: "Human advice", detail: "Compliant conversation", tone: "muted" },
          ],
        },
      },
    ],
  },
  "home-services": {
    introTitle: "Every missed ring is a job that went to the next contractor",
    introBody:
      "Home service brands pay for ads that still hit voicemail at lunch and after 5pm. Call & Flow answers, qualifies, and books so field teams keep rolling.",
    howTitle: "How Call & Flow works for home service businesses",
    howSupporting:
      "Unify answering across marketing numbers, qualify by trade, and book capacity-aware jobs with dispatch-friendly notes.",
    sections: [
      {
        id: "capture-demand",
        eyebrow: "Demand capture",
        title: "Answer every service request before the next company does",
        description:
          "Google, LSA, and referral calls deserve a live conversational answer — not a race to the voicemail beep.",
        bullets: [
          "Cover every marketing number consistently",
          "Capture job type, urgency, and address",
          "Book same-day or next available capacity",
          "Scale answering when ad spend spikes",
        ],
        tone: "surface",
        flow: {
          title: "Job intake",
          alt: "Home service job request answered and booked by AI receptionist",
          steps: [
            { label: "Service call", detail: "Needs help today" },
            { label: "AI receptionist", detail: "Job type + urgency", tone: "accent" },
            { label: "Qualify area", detail: "Coverage check" },
            { label: "Book job", detail: "Dispatch-ready", tone: "success" },
          ],
        },
      },
      {
        id: "multi-trade",
        eyebrow: "Multi-trade ready",
        title: "Use different scripts when HVAC, plumbing, and electrical differ",
        description:
          "One brand can still need separate intake logic per trade. Configure agents or knowledge sets accordingly.",
        bullets: [
          "Separate flows per trade when needed",
          "Keep emergency language accurate",
          "Route to the right ops owner",
          "Preserve a unified customer experience",
        ],
        tone: "bg",
        flow: {
          title: "Trade routing",
          alt: "Home services call routed to the correct trade workflow",
          steps: [
            { label: "Caller need", detail: "Which trade?" },
            { label: "Intent split", detail: "HVAC / plumbing / other", tone: "accent" },
            { label: "Trade script", detail: "Right questions" },
            { label: "Book / escalate", detail: "Correct path", tone: "success" },
          ],
        },
      },
      {
        id: "dispatch-notes",
        eyebrow: "Ops handoff",
        title: "Give dispatch notes teams can act on immediately",
        description:
          "Stop re-asking callers the same questions. Structured intake feeds the board your crews already use.",
        bullets: [
          "Consistent intake every time",
          "Dispatch-friendly summaries",
          "Fewer empty truck days from missed leads",
          "Human escalation for VIP or complex jobs",
        ],
        tone: "surface",
        cta: { href: "/pricing", label: "See plan limits" },
        flow: {
          title: "Dispatch ready",
          alt: "Home service call notes handed to dispatch after AI intake",
          steps: [
            { label: "Intake complete", detail: "Details captured" },
            { label: "Structured notes", detail: "Ops can read fast", tone: "accent" },
            { label: "Board update", detail: "Job visible", tone: "success" },
            { label: "Crew rolls", detail: "Prepared visit", tone: "muted" },
          ],
        },
      },
      {
        id: "after-hours-revenue",
        eyebrow: "After-hours revenue",
        title: "Stop paying for ads that ring into silence overnight",
        description:
          "Night callers become next-day booked work instead of abandoned opportunities.",
        bullets: [
          "Answer after 5pm and on weekends",
          "Book morning capacity",
          "Escalate true emergencies",
          "Protect campaign ROI",
        ],
        tone: "elevated",
        flow: {
          title: "Overnight",
          alt: "After-hours home service call converted into next-day booking",
          steps: [
            { label: "Night ring", detail: "Ads still running" },
            { label: "AI answers", detail: "Live conversation", tone: "accent" },
            { label: "Book morning", detail: "Capacity offered", tone: "success" },
            { label: "Lead kept", detail: "Not lost to voicemail", tone: "muted" },
          ],
        },
      },
    ],
  },
  "call-centers": {
    introTitle: "Not every call needs a live agent in the first minute",
    introBody:
      "Queues explode when volume spikes and agents repeat the same FAQs. Call & Flow contains repetitive work, identifies intent, and hands complex conversations to people with context.",
    howTitle: "How Call & Flow works for call centers",
    howSupporting:
      "Start with overflow or after-hours numbers, expand FAQ containment, and keep supervisors visible in the operations console.",
    sections: [
      {
        id: "containment",
        eyebrow: "FAQ containment",
        title: "Resolve documented questions before they burn a live seat",
        description:
          "Knowledge-grounded answers keep simple intents out of the queue while humans focus on exceptions.",
        bullets: [
          "Contain repetitive FAQs from approved content",
          "Identify intent before queueing",
          "Open follow-ups when offline work is needed",
          "Escalate cleanly when confidence is low",
        ],
        tone: "surface",
        cta: { href: "/use-cases/customer-support", label: "Customer support use case" },
        flow: {
          title: "Containment",
          alt: "Call center FAQ contained by AI voice agent before live queue",
          steps: [
            { label: "High volume", detail: "Queue pressure" },
            { label: "AI front end", detail: "Intent + FAQ", tone: "accent" },
            { label: "Resolve", detail: "Knowledge answer", tone: "success" },
            { label: "Or escalate", detail: "Live agent path", tone: "muted" },
          ],
        },
      },
      {
        id: "overflow",
        eyebrow: "Overflow cushion",
        title: "Absorb campaign spikes without catastrophic hold times",
        description:
          "Automation cushions peaks so service levels stay steadier without overstaffing every valley.",
        bullets: [
          "Handle overflow and after-hours demand",
          "Stabilize average speed of answer",
          "Reduce abandon rates on repetitive intents",
          "Keep supervisors informed via ops visibility",
        ],
        tone: "bg",
        flow: {
          title: "Overflow",
          alt: "Call center overflow handled by AI voice agents during spikes",
          steps: [
            { label: "Spike", detail: "Campaign or outage" },
            { label: "AI absorbs", detail: "Repetitive layer", tone: "accent" },
            { label: "Queue protected", detail: "Humans for exceptions", tone: "success" },
            { label: "SLA calmer", detail: "More stable service", tone: "muted" },
          ],
        },
      },
      {
        id: "context-handoff",
        eyebrow: "Context-rich handoff",
        title: "Stop making callers repeat themselves to live agents",
        description:
          "When a human joins, they should already know what was tried. Summaries shorten handle time on the live side.",
        bullets: [
          "Warm handoff with conversation summary",
          "Intent already identified",
          "Fewer repeated authentication loops",
          "Cleaner QA and coaching artifacts",
        ],
        tone: "surface",
        flow: {
          title: "Handoff",
          alt: "AI to human handoff in a call center with full context",
          steps: [
            { label: "Needs human", detail: "Exception case" },
            { label: "Summary ready", detail: "What AI already did", tone: "accent" },
            { label: "Live agent", detail: "Continues mid-flow", tone: "success" },
            { label: "Faster AHT", detail: "Less re-work", tone: "muted" },
          ],
        },
      },
      {
        id: "multi-client",
        eyebrow: "Multi-client ops",
        title: "Isolate client brands, numbers, and knowledge",
        description:
          "BPOs and agencies can run multiple clients on one platform without mixing data or voice.",
        bullets: [
          "Multi-tenant isolation by design",
          "Per-client numbers and knowledge",
          "Concurrent call capacity by plan",
          "Shared ops patterns with separate brands",
        ],
        tone: "elevated",
        flow: {
          title: "Multi-tenant",
          alt: "Multi-tenant call center AI isolation across client brands",
          steps: [
            { label: "Client A call", detail: "Isolated number" },
            { label: "Client knowledge", detail: "No cross-mix", tone: "accent" },
            { label: "Client B call", detail: "Separate brand", tone: "success" },
            { label: "Ops console", detail: "Supervisors see both safely", tone: "muted" },
          ],
        },
      },
    ],
  },
};

export const useCaseStories: Record<string, StoryPageContent> = {
  "appointment-booking": {
    introTitle: "Scheduling intent dies when nobody can offer a real time",
    introBody:
      "Callers who want an appointment should leave with a confirmed next step — not a promise that someone will call them back. Call & Flow books from real availability during the live conversation.",
    howTitle: "How appointment booking works in Call & Flow",
    howSupporting:
      "Connect booking rules, confirm required details, and escalate when a slot cannot be offered.",
    sections: [
      {
        id: "always-on-booking",
        eyebrow: "24/7 booking",
        title: "Let customers book appointments without waiting",
        description:
          "Your AI voice agent handles scheduling conversations and guides callers through the booking process while interest is high.",
        bullets: [
          "Answer booking calls immediately",
          "Collect required customer information",
          "Find available slots from your rules",
          "Confirm appointments before saving",
        ],
        tone: "surface",
        flow: {
          title: "Book now",
          alt: "Phone call to AI agent to calendar confirmed appointment workflow",
          steps: [
            { label: "Phone call", detail: "Wants a time" },
            { label: "AI agent", detail: "Scheduling intent", tone: "accent" },
            { label: "Calendar", detail: "Real availability" },
            { label: "Confirmed", detail: "Details verified", tone: "success" },
          ],
        },
      },
      {
        id: "smart-qualification",
        eyebrow: "Smart qualification",
        title: "Understand what the customer needs before booking",
        description:
          "Ask the questions that make the appointment useful — service type, location, and preferences — before locking a slot.",
        bullets: [
          "Ask configured discovery questions",
          "Identify service or visit type",
          "Collect customer details consistently",
          "Apply business rules before offering times",
        ],
        tone: "bg",
        flow: {
          title: "Qualify then book",
          alt: "AI qualifies service needs before offering appointment times",
          steps: [
            { label: "Caller need", detail: "Why they called" },
            { label: "Questions", detail: "Your booking fields", tone: "accent" },
            { label: "Fit check", detail: "Rules applied" },
            { label: "Offer slots", detail: "Only valid times", tone: "success" },
          ],
        },
      },
      {
        id: "confirmation",
        eyebrow: "Confirmation",
        title: "Give customers a clear next step",
        description:
          "Confirm what was booked, share instructions you approve, and support reschedule flows when enabled.",
        bullets: [
          "Confirm appointment details out loud",
          "Provide preparation instructions from knowledge",
          "Handle rescheduling and cancellation flows you enable",
          "Escalate when booking rules cannot satisfy the request",
        ],
        tone: "surface",
        flow: {
          title: "Confirm",
          alt: "Appointment confirmation and instructions delivered by AI voice agent",
          steps: [
            { label: "Slot chosen", detail: "Caller agrees" },
            { label: "Confirm", detail: "Time · place · contact", tone: "accent" },
            { label: "Instructions", detail: "Approved guidance" },
            { label: "Done", detail: "Trusted booking", tone: "success" },
          ],
        },
      },
      {
        id: "booking-handoff",
        eyebrow: "Human handoff",
        title: "Bring your team in when scheduling needs a person",
        description:
          "Complex calendars, VIP exceptions, and edge cases still reach humans — with context attached.",
        bullets: [
          "Transfer calls when configured",
          "Route by intent or department",
          "Preserve conversation context",
          "Follow your escalation workflows",
        ],
        tone: "elevated",
        cta: { href: "/pricing", label: "See pricing" },
        flow: {
          title: "Escalate",
          alt: "Complex booking request handed from AI to human scheduler",
          steps: [
            { label: "Edge case", detail: "Rules cannot book" },
            { label: "AI summarizes", detail: "What was tried", tone: "accent" },
            { label: "Human joins", detail: "Transfer or callback", tone: "success" },
            { label: "Resolved", detail: "Team owns exception", tone: "muted" },
          ],
        },
      },
    ],
  },
  "lead-qualification": {
    introTitle: "Inbound interest is worthless if nobody qualifies it in time",
    introBody:
      "Speed-to-lead and consistent discovery questions decide whether marketing spend becomes pipeline. Call & Flow qualifies while the caller is still engaged.",
    howTitle: "How lead qualification works in Call & Flow",
    howSupporting:
      "Define the questions that mark a sales-ready lead, then route or book the next conversation.",
    sections: [
      {
        id: "immediate-response",
        eyebrow: "Immediate response",
        title: "Qualify leads while interest is still high",
        description:
          "Every delayed callback is a competitor’s opportunity. Answer, ask discovery questions, and capture contact details on the first call.",
        bullets: [
          "Answer inbound marketing calls instantly",
          "Run your discovery script conversationally",
          "Capture name, phone, email, and company fields you allow",
          "Book demos or estimates before hang-up",
        ],
        tone: "surface",
        flow: {
          title: "Qualify now",
          alt: "Inbound lead qualified by AI agent into CRM for sales",
          steps: [
            { label: "Caller", detail: "Inbound interest" },
            { label: "AI agent", detail: "Discovery questions", tone: "accent" },
            { label: "Qualification", detail: "Fit by your rules" },
            { label: "CRM + sales", detail: "Rep notified", tone: "success" },
          ],
        },
      },
      {
        id: "consistent-scoring",
        eyebrow: "Consistent intake",
        title: "Stop every rep from asking a different set of questions",
        description:
          "Structured qualification means cleaner pipeline data and fewer unqualified meetings.",
        bullets: [
          "Same critical fields every time",
          "Intent and timeline captured up front",
          "Service-area or ICP filters you configure",
          "Fewer calendar burns on bad-fit demos",
        ],
        tone: "bg",
        flow: {
          title: "Structured",
          alt: "Consistent lead qualification fields captured by AI voice agent",
          steps: [
            { label: "Lead arrives", detail: "Any channel to phone" },
            { label: "Scripted ask", detail: "Your ICP questions", tone: "accent" },
            { label: "Fields saved", detail: "Structured notes", tone: "success" },
            { label: "Clean handoff", detail: "Sales starts informed", tone: "muted" },
          ],
        },
      },
      {
        id: "route-intent",
        eyebrow: "Intent routing",
        title: "Send sales-ready callers one place — support another",
        description:
          "Not every ring is a lead. Route by intent so sales time stays on closable conversations.",
        bullets: [
          "Separate sales, support, and booking intents",
          "Transfer hot leads when a human should join",
          "Nurture or message paths for not-yet-ready callers",
          "Protect SDR and AE calendars",
        ],
        tone: "surface",
        flow: {
          title: "Route",
          alt: "Lead intent routing between sales and support with AI",
          steps: [
            { label: "Intent", detail: "Sales vs support" },
            { label: "Branch", detail: "Configured paths", tone: "accent" },
            { label: "Hot lead", detail: "Sales queue", tone: "success" },
            { label: "Other intents", detail: "Support / booking", tone: "muted" },
          ],
        },
      },
      {
        id: "sales-ready",
        eyebrow: "Sales-ready handoff",
        title: "Give closers answers, not detective work",
        description:
          "When a human takes over, the basics are already collected and the next step is clear.",
        bullets: [
          "Context-rich transfer or callback",
          "Demo or estimate already offered when possible",
          "CRM-oriented notes for follow-up",
          "Better use of the same ad spend",
        ],
        tone: "elevated",
        cta: { href: "/use-cases/sales-calls", label: "Sales calls use case" },
        flow: {
          title: "Closer ready",
          alt: "Qualified lead handed to sales rep with AI conversation context",
          steps: [
            { label: "Qualified", detail: "Fit confirmed" },
            { label: "Summary", detail: "Discovery complete", tone: "accent" },
            { label: "Sales rep", detail: "Joins prepared", tone: "success" },
            { label: "Advance deal", detail: "Human relationship", tone: "muted" },
          ],
        },
      },
    ],
  },
  "customer-support": {
    introTitle: "Support queues fill with questions you have already documented",
    introBody:
      "Repetitive FAQs burn expensive agent time when answers already exist in your knowledge base. Call & Flow resolves what it can — and escalates the rest with context.",
    howTitle: "How AI customer support works in Call & Flow",
    howSupporting:
      "Ground answers in approved documents, open follow-ups when needed, and hand off account issues cleanly.",
    sections: [
      {
        id: "knowledge-answers",
        eyebrow: "Knowledge-grounded answers",
        title: "Resolve FAQs without inventing policy",
        description:
          "Support automation only helps when it stays tied to approved content. Unknown answers should escalate — not improvise.",
        bullets: [
          "Answer from documents you approve",
          "Keep policy language consistent",
          "Say when information is unavailable",
          "Reduce live-agent load on repetitive intents",
        ],
        tone: "surface",
        flow: {
          title: "Knowledge",
          alt: "Support call answered from knowledge base by AI voice agent",
          steps: [
            { label: "Caller", detail: "Support question" },
            { label: "AI agent", detail: "Searches knowledge", tone: "accent" },
            { label: "Answer", detail: "Approved content", tone: "success" },
            { label: "Or escalate", detail: "If unknown", tone: "muted" },
          ],
        },
      },
      {
        id: "follow-ups",
        eyebrow: "Follow-ups",
        title: "Open the right next task when the issue needs offline work",
        description:
          "Not every support call resolves on the spot. Create callback or ticket-style follow-ups your team can work.",
        bullets: [
          "Capture issue details consistently",
          "Create follow-up tasks when configured",
          "Keep callers informed about next steps",
          "Avoid false ‘it’s fixed’ moments",
        ],
        tone: "bg",
        flow: {
          title: "Follow-up",
          alt: "Support issue turned into a follow-up task by AI agent",
          steps: [
            { label: "Complex issue", detail: "Needs offline work" },
            { label: "Details captured", detail: "Structured notes", tone: "accent" },
            { label: "Follow-up opened", detail: "Team queue", tone: "success" },
            { label: "Human resolves", detail: "Async completion", tone: "muted" },
          ],
        },
      },
      {
        id: "after-hours-support",
        eyebrow: "After-hours support",
        title: "Keep answering when the support floor is closed",
        description:
          "Thin overnight staffing should not mean abandoned customers. Cover FAQs and capture escalations.",
        bullets: [
          "Answer after-hours support lines",
          "Contain documented questions overnight",
          "Escalate urgent account issues per rules",
          "Protect CSAT when volume is uneven",
        ],
        tone: "surface",
        flow: {
          title: "After hours",
          alt: "After-hours customer support coverage with AI voice agent",
          steps: [
            { label: "Night call", detail: "Floor closed" },
            { label: "AI covers", detail: "FAQ + intake", tone: "accent" },
            { label: "Resolve / queue", detail: "Clear next step", tone: "success" },
            { label: "Morning team", detail: "Picks up context", tone: "muted" },
          ],
        },
      },
      {
        id: "support-handoff",
        eyebrow: "Human handoff",
        title: "Escalate account issues with the story already written",
        description:
          "Live agents should not start from zero. Context-rich handoffs shorten handle time and reduce caller frustration.",
        bullets: [
          "Transfer with conversation summary",
          "Identify that a human is required early",
          "Work alongside existing call-center teams",
          "Keep sensitive cases with people",
        ],
        tone: "elevated",
        cta: { href: "/industries/call-centers", label: "Call centers" },
        flow: {
          title: "Escalate",
          alt: "Customer support AI handing off to a human agent with context",
          steps: [
            { label: "Needs human", detail: "Account / exception" },
            { label: "Summary", detail: "What was tried", tone: "accent" },
            { label: "Live agent", detail: "Continues call", tone: "success" },
            { label: "Faster resolve", detail: "Less repetition", tone: "muted" },
          ],
        },
      },
    ],
  },
  "call-answering": {
    introTitle: "Voicemail is a conversion dead end for busy business lines",
    introBody:
      "Missed calls are missed revenue. Call & Flow answers every ring with an on-brand AI receptionist that can book, qualify, message, and escalate — including nights and weekends.",
    howTitle: "How AI call answering works in Call & Flow",
    howSupporting:
      "Greet in your brand voice, detect intent, complete the next step, and keep after-hours playbooks consistent.",
    sections: [
      {
        id: "always-on-answer",
        eyebrow: "Always-on answering",
        title: "Pick up when your team cannot",
        description:
          "Campaign spikes, lunch rushes, and after-hours rings still get a helpful conversation on the first try.",
        bullets: [
          "Answer inbound business lines immediately",
          "Greet in your brand voice",
          "Cover nights, weekends, and holidays",
          "Stop paying for ads that hit silence",
        ],
        tone: "surface",
        flow: {
          title: "Answer",
          alt: "Incoming business call answered by AI receptionist and routed",
          steps: [
            { label: "Incoming call", detail: "Never to voicemail" },
            { label: "AI receptionist", detail: "Brand greeting", tone: "accent" },
            { label: "Intent", detail: "Why they called" },
            { label: "Route", detail: "Answer · book · transfer", tone: "success" },
          ],
        },
      },
      {
        id: "intent-detection",
        eyebrow: "Intent detection",
        title: "Understand what the caller needs before routing",
        description:
          "Booking, support, sales, and emergencies deserve different paths. Detect intent early and send the conversation the right way.",
        bullets: [
          "Identify booking, support, and sales intents",
          "Apply after-hours vs business-hours rules",
          "Capture structured messages when humans are unavailable",
          "Keep every line sounding professional",
        ],
        tone: "bg",
        flow: {
          title: "Intent",
          alt: "AI receptionist detecting caller intent and choosing a workflow",
          steps: [
            { label: "Caller speaks", detail: "Natural language" },
            { label: "Intent found", detail: "Book / FAQ / human", tone: "accent" },
            { label: "Workflow", detail: "Correct path starts", tone: "success" },
            { label: "Outcome", detail: "Next step clear", tone: "muted" },
          ],
        },
      },
      {
        id: "multi-number",
        eyebrow: "Multi-number coverage",
        title: "Give every marketing line the same reliable front door",
        description:
          "Plans include phone number allowances so campaigns and locations can share a consistent answering standard.",
        bullets: [
          "Configure different scripts per number when needed",
          "Keep brand voice consistent across lines",
          "Cover overflow when the main line is busy",
          "Monitor outcomes from one console",
        ],
        tone: "surface",
        cta: { href: "/pricing", label: "Number limits by plan" },
        flow: {
          title: "Numbers",
          alt: "Multiple business phone numbers covered by AI call answering",
          steps: [
            { label: "Line A / B / C", detail: "Campaigns · locations" },
            { label: "AI answers", detail: "Configured per line", tone: "accent" },
            { label: "Shared standard", detail: "Professional every time", tone: "success" },
            { label: "Ops view", detail: "One console", tone: "muted" },
          ],
        },
      },
      {
        id: "answering-handoff",
        eyebrow: "Human handoff",
        title: "Message, transfer, or escalate — with context",
        description:
          "Answering is only useful if urgent callers still reach people. Preserve context either way.",
        bullets: [
          "Live transfer when available",
          "Structured message taking as fallback",
          "Emergency playbooks you define",
          "Fewer abandoned opportunities",
        ],
        tone: "elevated",
        flow: {
          title: "Handoff",
          alt: "AI call answering escalating to a human with message context",
          steps: [
            { label: "Needs person", detail: "Urgent or complex" },
            { label: "AI prepares", detail: "Notes ready", tone: "accent" },
            { label: "Transfer / message", detail: "Per availability", tone: "success" },
            { label: "Human follows", detail: "Informed callback", tone: "muted" },
          ],
        },
      },
    ],
  },
  "sales-calls": {
    introTitle: "Inbound sales opportunities expire while reps are already on demos",
    introBody:
      "High-intent callers should not land in voicemail. Call & Flow sales agents capture details, qualify interest, and book the next conversation — then hand off to closers with context.",
    howTitle: "How inbound sales calls work in Call & Flow",
    howSupporting:
      "Configure a sales-oriented agent for qualification, booking, and live transfer when a closer should join immediately.",
    sections: [
      {
        id: "capture-inbound",
        eyebrow: "Inbound capture",
        title: "Turn high-intent rings into demos and estimates",
        description:
          "Answer with sales-ready energy, run discovery, and book while the caller is still motivated.",
        bullets: [
          "Greet inbound opportunities immediately",
          "Capture contact and company details",
          "Ask discovery questions your process requires",
          "Book demos or estimates on the spot",
        ],
        tone: "surface",
        flow: {
          title: "Inbound sales",
          alt: "Inbound sales lead handled by AI agent into CRM and sales rep",
          steps: [
            { label: "Lead", detail: "High-intent call" },
            { label: "AI agent", detail: "Qualify + capture", tone: "accent" },
            { label: "CRM", detail: "Structured notes" },
            { label: "Sales rep", detail: "Closer ready", tone: "success" },
          ],
        },
      },
      {
        id: "consistent-first-response",
        eyebrow: "Consistent first response",
        title: "Every sales call gathers the same critical fields",
        description:
          "CRM quality improves when intake is not improvised differently by whoever happened to pick up.",
        bullets: [
          "Standard qualification fields",
          "Clear fit / not-fit branching",
          "Fewer ‘what did they say?’ gaps",
          "Reps spend time selling, not re-asking basics",
        ],
        tone: "bg",
        cta: { href: "/use-cases/lead-qualification", label: "Lead qualification" },
        flow: {
          title: "Consistency",
          alt: "Consistent inbound sales qualification fields captured by AI",
          steps: [
            { label: "Opportunity", detail: "Any inbound line" },
            { label: "Same script", detail: "Critical fields", tone: "accent" },
            { label: "Notes saved", detail: "CRM-ready", tone: "success" },
            { label: "Rep advances", detail: "Informed close", tone: "muted" },
          ],
        },
      },
      {
        id: "book-next-step",
        eyebrow: "Next-step booking",
        title: "Do not let hot leads wait a day for scheduling",
        description:
          "Even interested buyers bounce when booking the next conversation takes another round of phone tag.",
        bullets: [
          "Offer demo or estimate slots live",
          "Confirm details before saving",
          "Reduce no-show risk with clear confirmation",
          "Escalate when calendars need a human",
        ],
        tone: "surface",
        flow: {
          title: "Book next step",
          alt: "Sales demo booked during inbound AI phone conversation",
          steps: [
            { label: "Qualified yes", detail: "Buyer engaged" },
            { label: "Offer slot", detail: "Demo / estimate", tone: "accent" },
            { label: "Confirm", detail: "Time locked", tone: "success" },
            { label: "Closer calendar", detail: "Ready to meet", tone: "muted" },
          ],
        },
      },
      {
        id: "closer-transfer",
        eyebrow: "Closer transfer",
        title: "Hand off immediately when a human should own the close",
        description:
          "Some conversations should not wait for a booked demo. Transfer hot leads live with the discovery already done.",
        bullets: [
          "Live transfer to closers when available",
          "Context attached — no cold starts",
          "Works for roofing, real estate, legal, insurance, and more",
          "Keeps AI on first response, humans on relationships",
        ],
        tone: "elevated",
        cta: { href: "/signup", label: "Start free trial" },
        flow: {
          title: "Live close",
          alt: "Hot inbound sales lead transferred from AI agent to closer",
          steps: [
            { label: "Hot now", detail: "Wants a person" },
            { label: "AI summary", detail: "Discovery done", tone: "accent" },
            { label: "Live transfer", detail: "Closer joins", tone: "success" },
            { label: "Human close", detail: "Relationship selling", tone: "muted" },
          ],
        },
      },
    ],
  },
};

export function getIndustryStory(slug: string): StoryPageContent | undefined {
  return industryStories[slug];
}

export function getUseCaseStory(slug: string): StoryPageContent | undefined {
  return useCaseStories[slug];
}
