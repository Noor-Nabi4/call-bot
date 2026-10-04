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
          "If your primary search is for an AI receptionist for small business, start on the AI receptionist page, then review pricing based on included voice minutes and concurrency — not vague per-seat promises.",
        ],
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
  },
] as const;

export function getBlogPost(slug: string): BlogPost | undefined {
  return blogPosts.find((post) => post.slug === slug);
}

export function getBlogSlugs(): string[] {
  return blogPosts.map((post) => post.slug);
}
