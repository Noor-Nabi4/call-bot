/** Blog foundation — high-quality posts only; expand over time. */

export type BlogPost = {
  slug: string;
  title: string;
  description: string;
  publishedAt: string;
  updatedAt: string;
  readingMinutes: number;
  tags: readonly string[];
  /** Plain sections rendered as article body. */
  sections: readonly { heading?: string; paragraphs: readonly string[] }[];
  /** Commercial deep links rendered via RelatedLinks. */
  relatedLinks?: readonly {
    href: string;
    label: string;
    description: string;
  }[];
};

export const blogIndex = {
  title: "Resources on AI Voice Agents & Business Phone Automation",
  description:
    "Practical guides on AI receptionists, AI voice agents, and business phone automation for US service businesses and call centers.",
  h1: "Call & Flow Resources",
  supporting:
    "Straightforward writing for operators evaluating AI voice agents — no hype, no fake case studies.",
} as const;

export const blogPosts: readonly BlogPost[] = [
  {
    slug: "what-is-an-ai-receptionist",
    title: "What Is an AI Receptionist? A Practical Guide for US Businesses",
    description:
      "Learn what an AI receptionist is, how it answers business phone calls, when to use human handoff, and how it differs from a traditional answering service.",
    publishedAt: "2026-09-15",
    updatedAt: "2026-09-15",
    readingMinutes: 6,
    tags: ["AI receptionist", "AI voice agents", "Call answering"],
    sections: [
      {
        paragraphs: [
          "An AI receptionist is a voice agent that answers your business phone line, greets callers in your brand voice, and completes front-desk tasks — like answering hours questions, booking appointments, capturing lead details, and transferring urgent calls to a person.",
          "Unlike a basic IVR menu (“press 1 for sales”), a modern AI receptionist holds a conversation. Callers can speak naturally about why they are calling, and the agent follows the workflows you configure.",
        ],
      },
      {
        heading: "What an AI receptionist can do",
        paragraphs: [
          "Most US small businesses adopt AI receptionists for a familiar set of jobs: answer every call, cover after hours, book appointments, qualify inbound leads, and take structured messages when nobody is available.",
          "The best implementations stay grounded. Answers to FAQs should come from an approved knowledge base. Appointment times should come from real availability rules. Anything the agent cannot do should escalate to a human instead of being invented.",
        ],
      },
      {
        heading: "AI receptionist vs traditional answering service",
        paragraphs: [
          "Traditional answering services often specialize in message taking. That still beats voicemail, but it rarely books the appointment or qualifies the job while the caller is on the line.",
          "An AI receptionist service can complete more of the workflow in one conversation — then hand off to your team with context when a person is required.",
        ],
      },
      {
        heading: "When you still need a human",
        paragraphs: [
          "AI should not pretend to be a doctor, lawyer, or insurance adjuster. Sensitive, emotional, or highly complex calls belong with people. The product win is making sure those humans receive a clean summary instead of a cold transfer with no context.",
          "If you are evaluating platforms, look for booking you can trust, knowledge grounding, after-hours rules, and human handoff — not just a demo that sounds impressive for thirty seconds.",
        ],
      },
      {
        heading: "Getting started with Call & Flow",
        paragraphs: [
          "Call & Flow is an AI voice agent platform for service businesses and call centers. You can try a live browser voice demo, start a free trial, configure an industry template, and connect a business number when you are ready.",
          "If your primary search is for an AI receptionist for small business, start on the AI receptionist product page, then review pricing based on included voice minutes and concurrency — not vague per-seat promises.",
        ],
      },
    ],
    relatedLinks: [
      {
        href: "/ai-receptionist",
        label: "AI Receptionist",
        description: "Product page for front-desk answering and booking.",
      },
      {
        href: "/use-cases/call-answering",
        label: "AI call answering",
        description: "Workflow for overflow and after-hours coverage.",
      },
      {
        href: "/pricing",
        label: "Pricing",
        description: "Minutes, concurrency, and plan limits.",
      },
    ],
  },
  {
    slug: "ai-voice-agents-vs-chatbots",
    title: "AI Voice Agents vs Chatbots: Why Phone Still Matters",
    description:
      "Chatbots help on your website. AI voice agents answer the phone. Here is how they differ for US service businesses that win or lose jobs on the first call.",
    publishedAt: "2026-09-22",
    updatedAt: "2026-09-22",
    readingMinutes: 5,
    tags: ["AI voice agents", "Business phone automation"],
    sections: [
      {
        paragraphs: [
          "Chatbots and AI voice agents both use language models, but they sit in different moments of the customer journey. A chatbot waits for someone to visit your site. An AI voice agent answers the number printed on your truck, Google Business Profile, and ads.",
          "For plumbers, clinics, law firms, and agencies, that distinction matters. High-intent buyers still call — especially for urgent or high-consideration services.",
        ],
      },
      {
        heading: "Different interfaces, different expectations",
        paragraphs: [
          "On chat, users tolerate a little back-and-forth typing. On the phone, long silences and robotic menus feel broken. Voice agents need low latency, clear turn-taking, and an obvious path to a human.",
          "They also need tools. Booking, lead capture, and handoff are not “nice to have” — they are why someone called instead of filling out a form.",
        ],
      },
      {
        heading: "When to use both",
        paragraphs: [
          "Many teams should use both: chat for website FAQs and after-hours web visitors, voice for inbound phone demand. The mistake is assuming a website widget replaces the business line.",
          "If your ads and local listings drive calls, invest in AI call answering and AI voice agents that can complete the job on the phone — then connect that workflow to the same operations habits your staff already use.",
        ],
      },
    ],
    relatedLinks: [
      {
        href: "/ai-voice-agents",
        label: "AI Voice Agents",
        description: "Platform overview for business phone automation.",
      },
      {
        href: "/use-cases/call-answering",
        label: "AI call answering",
        description: "Keep the business line answered when chat is not enough.",
      },
    ],
  },
  {
    slug: "ai-receptionist-vs-traditional-answering-service",
    title: "AI Receptionist vs Traditional Answering Service",
    description:
      "Compare AI receptionists and traditional answering services for booking, qualification, after-hours coverage, and human handoff — without hype or invented stats.",
    publishedAt: "2026-10-01",
    updatedAt: "2026-10-01",
    readingMinutes: 8,
    tags: [
      "AI receptionist",
      "AI answering service",
      "traditional answering service",
    ],
    sections: [
      {
        paragraphs: [
          "When a business line rings and nobody is free, most teams reach for one of two fixes: a traditional answering service or an AI receptionist. Both can beat voicemail. They are not interchangeable.",
          "This article explains the practical differences US operators should weigh — message taking versus completed work, cost structure, after-hours coverage, and when a human still needs to join.",
        ],
      },
      {
        heading: "What a traditional answering service usually does",
        paragraphs: [
          "A live answering service typically greets the caller, takes a message, and relays that message to your team. Some services offer limited scheduling or dispatch scripts, but many still specialize in capture and callback.",
          "That model works when your main gap is a missed greeting. It is weaker when the caller is ready to book, share job details, or finish a qualification script on the first conversation.",
        ],
      },
      {
        heading: "What an AI receptionist is built to finish",
        paragraphs: [
          "An AI receptionist is a voice agent configured as your front desk. Beyond greeting, it can answer approved FAQs, offer real appointment availability, capture structured lead details, and escalate to a person with context.",
          "The quality bar is grounding: booking times should come from real rules, FAQ answers from documents you approve, and anything uncertain should transfer or queue a callback instead of inventing an answer.",
        ],
      },
      {
        heading: "Where each option fits",
        paragraphs: [
          "Choose a traditional service if you primarily need a human message taker and your team will complete every next step later. Choose an AI receptionist when missed calls should still convert into booked appointments, qualified leads, or routed support during the same conversation.",
          "Many teams blend both ideas: AI handles the first line and after-hours volume, while humans take over for complex, emotional, or high-risk calls. The important part is that the handoff includes a summary — not a cold transfer.",
        ],
      },
      {
        heading: "Questions to ask before you switch",
        paragraphs: [
          "Ask how booking availability is enforced, what happens when the agent does not know an answer, how after-hours emergencies are routed, and whether your team can review call outcomes in one place.",
          "If you are evaluating Call & Flow, start with the AI receptionist product page for the category overview, the call answering use case for overflow coverage, and pricing for minute and concurrency limits.",
        ],
      },
    ],
    relatedLinks: [
      {
        href: "/ai-receptionist",
        label: "AI Receptionist",
        description: "Front-desk AI answering, booking, and handoff.",
      },
      {
        href: "/use-cases/call-answering",
        label: "AI call answering",
        description: "Overflow and after-hours coverage workflow.",
      },
      {
        href: "/pricing",
        label: "Pricing",
        description: "Compare plans by minutes and concurrency.",
      },
    ],
  },
  {
    slug: "how-much-does-an-ai-receptionist-cost",
    title: "How Much Does an AI Receptionist Cost?",
    description:
      "A practical guide to AI receptionist pricing: voice minutes, concurrency, phone numbers, users, and knowledge limits — without invented averages.",
    publishedAt: "2026-10-02",
    updatedAt: "2026-10-02",
    readingMinutes: 7,
    tags: ["AI receptionist cost", "AI voice agent pricing", "pricing"],
    sections: [
      {
        paragraphs: [
          "AI receptionist pricing is easier to understand when you ignore vague “per seat” marketing and look at what actually drives cost on a phone platform: voice minutes, how many calls can run at once, how many numbers you need, and how much knowledge the agent can use.",
          "This guide explains those levers in plain language so you can compare plans without relying on fabricated industry averages.",
        ],
      },
      {
        heading: "Voice minutes are the core meter",
        paragraphs: [
          "Most AI phone platforms meter conversation time. A busy home-services company that answers every overflow call will consume more minutes than a quiet office that only covers lunch.",
          "When you estimate usage, think about peak days, after-hours coverage, and average call length for booking or intake — then leave headroom for busy season.",
        ],
      },
      {
        heading: "Concurrency, numbers, and team access",
        paragraphs: [
          "Concurrency is how many AI calls can happen at the same time. If two customers call during a storm spike, you need more than one concurrent session.",
          "Phone number limits matter if you run locations or campaigns on separate lines. User seats matter if multiple people need ops access to review calls, appointments, and handoffs.",
        ],
      },
      {
        heading: "Knowledge and workflow complexity",
        paragraphs: [
          "Answering FAQs from approved documents usually costs less operational risk than inventing answers. Plans that include knowledge limits are really about how much grounded content your agent can use.",
          "Booking and qualification workflows do not require custom model training to start, but they do require clear rules. The cleaner your availability and escalation rules, the less human cleanup you pay for later.",
        ],
      },
      {
        heading: "How to evaluate Call & Flow specifically",
        paragraphs: [
          "Call & Flow publishes Starter, Growth, Pro, and Enterprise plan structures based on included minutes, concurrency, numbers, users, and knowledge. Review the live pricing page for current numbers and overage rates rather than relying on a blog snapshot.",
          "If cost is your main question, pair the pricing page with the AI receptionist product page so you are buying the right workflow — not just the cheapest minute pool.",
        ],
      },
    ],
    relatedLinks: [
      {
        href: "/pricing",
        label: "Pricing",
        description: "Current plans, minutes, and concurrency limits.",
      },
      {
        href: "/ai-receptionist",
        label: "AI Receptionist",
        description: "What the product includes before you compare plans.",
      },
    ],
  },
  {
    slug: "ai-answering-service-for-hvac-companies",
    title: "AI Answering Service for HVAC Companies",
    description:
      "How HVAC companies use AI call answering for no-cool emergencies, maintenance booking, estimate intake, and after-hours coverage — without inventing dispatch promises.",
    publishedAt: "2026-10-03",
    updatedAt: "2026-10-03",
    readingMinutes: 8,
    tags: ["HVAC", "AI answering service", "AI receptionist"],
    sections: [
      {
        paragraphs: [
          "HVAC companies lose jobs when the phone goes unanswered during peak season. Homeowners calling about no cool or no heat rarely wait through a long voicemail. An AI answering service gives the first line a consistent intake path while techs stay on the road.",
          "This article is a practical companion to the HVAC industry page. It focuses on call patterns and playbooks, not a replacement for the commercial lander.",
        ],
      },
      {
        heading: "The calls that matter most",
        paragraphs: [
          "Emergency no-cool or no-heat calls need address, symptoms, and urgency captured quickly. Maintenance plan bookings need account details and open slots. Estimate requests need property context and a clean callback or site-visit booking.",
          "If those three call types share one overloaded CSR, peak season becomes a queue of half-finished notes. AI call answering can take the first pass and keep the structure consistent.",
        ],
      },
      {
        heading: "What good HVAC phone automation looks like",
        paragraphs: [
          "A useful HVAC voice workflow greets in your brand voice, distinguishes emergency language from routine service, checks service area when you configure it, and books the next available diagnostic or maintenance window from real rules.",
          "It should not invent same-day promises or pricing. When a true emergency needs a person, it should escalate with the summary already attached.",
        ],
      },
      {
        heading: "After-hours is part of the product",
        paragraphs: [
          "Many HVAC ads run into evenings and weekends. An AI answering path can book next-day service, capture emergency details, or follow your on-call transfer rules instead of dumping every midnight ring onto one owner’s cell phone with no context.",
          "Start with the HVAC industry page for the full commercial workflow, then review call answering and appointment booking use cases for the specific outcomes you want first.",
        ],
      },
    ],
    relatedLinks: [
      {
        href: "/industries/hvac",
        label: "AI receptionist for HVAC",
        description: "Industry lander for HVAC call workflows.",
      },
      {
        href: "/ai-receptionist",
        label: "AI Receptionist",
        description: "Product category for front-desk answering.",
      },
      {
        href: "/use-cases/call-answering",
        label: "AI call answering",
        description: "Overflow and after-hours coverage use case.",
      },
    ],
  },
  {
    slug: "ai-receptionist-for-dental-offices",
    title: "AI Receptionist for Dental Offices: What to Automate First",
    description:
      "A practical guide for dental offices evaluating an AI receptionist for hygiene booking, new-patient intake, FAQs, and after-hours tooth-pain routing — without clinical advice.",
    publishedAt: "2026-10-04",
    updatedAt: "2026-10-04",
    readingMinutes: 7,
    tags: ["Dental", "AI receptionist", "appointment booking"],
    sections: [
      {
        paragraphs: [
          "Dental front desks juggle check-in, insurance questions, and a constant stream of phone calls. An AI receptionist can take the repetitive scheduling and FAQ load so staff stay available for patients in the office.",
          "This guide supports the dental industry page. It explains what to automate first and what should stay with humans.",
        ],
      },
      {
        heading: "Start with hygiene and exam booking",
        paragraphs: [
          "Existing patients calling for cleanings are high-volume and structured. If your scheduling rules are connected, an AI receptionist can offer open times, confirm patient details, and reduce voicemail for rebooks.",
          "New-patient intake can come next: capture preferred times, reason for visit, and the insurance process details you allow — then book or escalate according to your script.",
        ],
      },
      {
        heading: "Keep clinical judgment with your team",
        paragraphs: [
          "Tooth-pain and treatment-plan questions need careful handling. The right automation path is empathy plus a scripted next step — not a diagnosis. Escalate symptom-related calls per your office rules.",
          "Approved FAQs about hours, parking, and financing pages are safer automation targets because they come from content you publish and control.",
        ],
      },
      {
        heading: "How this differs from the dental industry lander",
        paragraphs: [
          "The dental industry page is the commercial conversion page for practices ready to evaluate Call & Flow. This article is the educational walkthrough of what to automate first and why appointment booking is usually the highest-ROI starting workflow.",
          "When you are ready, pair the dental lander with the appointment booking use case and the AI receptionist product page.",
        ],
      },
    ],
    relatedLinks: [
      {
        href: "/industries/dental",
        label: "AI receptionist for dental offices",
        description: "Industry lander for dental phone workflows.",
      },
      {
        href: "/use-cases/appointment-booking",
        label: "AI appointment booking",
        description: "Book visits during the live call.",
      },
      {
        href: "/ai-receptionist",
        label: "AI Receptionist",
        description: "Product overview for front-desk automation.",
      },
    ],
  },
  {
    slug: "how-ai-appointment-booking-works",
    title: "How AI Appointment Booking Works on Business Phone Calls",
    description:
      "Learn how AI appointment booking collects intent, checks real availability, confirms details, and escalates when a human should finish the schedule.",
    publishedAt: "2026-10-05",
    updatedAt: "2026-10-05",
    readingMinutes: 7,
    tags: ["AI appointment booking", "AI receptionist", "scheduling"],
    sections: [
      {
        paragraphs: [
          "AI appointment booking is not “the chatbot guesses a time.” On a business phone call, it is a structured workflow: understand why the caller needs a visit, offer availability from rules you configure, confirm the details that matter, and save the appointment — or escalate cleanly when booking is not possible.",
          "This article explains that flow for operators evaluating phone scheduling automation.",
        ],
      },
      {
        heading: "Step 1: Capture booking intent",
        paragraphs: [
          "Callers rarely start with a perfect request. They say “I need a cleaning,” “Can someone look at my AC Friday?” or “I want a consult next week.” The agent’s first job is to identify booking intent and the service type your calendar cares about.",
          "If the request is not a booking — for example a billing dispute — the conversation should route to support or a human instead of forcing a calendar path.",
        ],
      },
      {
        heading: "Step 2: Offer real availability",
        paragraphs: [
          "Trust breaks when an agent invents an open slot. Good systems present windows from configured availability and capacity rules. If nothing fits, the agent should say so and offer the next allowed action: waitlist, callback, or human transfer.",
          "Confirmation details — name, phone, service notes, and any location or provider preferences — should be verified before the appointment is written.",
        ],
      },
      {
        heading: "Step 3: Save, notify, and hand off exceptions",
        paragraphs: [
          "After confirmation, the appointment should land where your team already works. Exceptions such as complex multi-resource jobs or VIP accounts can escalate with the conversation summary attached.",
          "Industries that benefit first include dental, healthcare clinics, HVAC, and real estate showings — anywhere a missed scheduling call becomes a missed day on the calendar.",
        ],
      },
      {
        heading: "Where to go next",
        paragraphs: [
          "For the commercial workflow page, open the appointment booking use case. For industry-specific scheduling context, review dental, healthcare, or HVAC. For the broader front-desk product, start with AI Receptionist.",
        ],
      },
    ],
    relatedLinks: [
      {
        href: "/use-cases/appointment-booking",
        label: "AI appointment booking",
        description: "Use-case lander for phone scheduling.",
      },
      {
        href: "/industries/dental",
        label: "Dental",
        description: "Hygiene and exam booking context.",
      },
      {
        href: "/industries/hvac",
        label: "HVAC",
        description: "Service and maintenance scheduling context.",
      },
      {
        href: "/ai-receptionist",
        label: "AI Receptionist",
        description: "Front-desk product that includes booking.",
      },
    ],
  },
] as const;

export function getBlogPost(slug: string): BlogPost | undefined {
  return blogPosts.find((post) => post.slug === slug);
}

export function getBlogSlugs(): string[] {
  return blogPosts.map((post) => post.slug);
}
