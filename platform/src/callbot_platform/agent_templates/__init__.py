"""Industry agent templates — config only, no industry branches in voice logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SuggestedArticle:
    category: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IndustryTemplate:
    key: str
    name: str
    description: str
    agent_type: str
    greeting: str
    tone: str
    response_style: str
    business_description: str
    booking_rules: str | None
    pricing_disclosure_policy: str | None
    handoff_rules_text: str | None
    restricted_topics: list[str]
    custom_instructions: str | None
    enabled_tools: dict[str, bool]
    example_questions: list[str]
    suggested_articles: list[SuggestedArticle] = field(default_factory=list)
    category: str = "General"
    marketplace_blurb: str | None = None
    featured: bool = False

    def profile_defaults(self) -> dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "industry_key": self.key,
            "greeting": self.greeting,
            "tone": self.tone,
            "response_style": self.response_style,
            "business_description": self.business_description,
            "booking_rules": self.booking_rules,
            "pricing_disclosure_policy": self.pricing_disclosure_policy,
            "handoff_rules_text": self.handoff_rules_text,
            "restricted_topics": list(self.restricted_topics),
            "custom_instructions": self.custom_instructions,
            "enabled_tools": dict(self.enabled_tools),
        }

    def summarize(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "category": self.category,
            "marketplace_blurb": self.marketplace_blurb or self.description,
            "featured": self.featured,
            "example_questions": list(self.example_questions),
            "enabled_tools": dict(self.enabled_tools),
            "suggested_article_count": len(self.suggested_articles),
        }


_ALL_TOOLS = {
    "crm": True,
    "scheduling": True,
    "knowledge": True,
    "handoff": True,
    "sms": True,
}

_CATEGORY_BY_TYPE = {
    "receptionist": "Field service",
    "booking": "Appointments",
    "support": "Support",
    "sales": "Sales",
    "help_desk": "Support",
    "call_center": "Call center",
    "custom": "General",
}


def _tpl(
    *,
    key: str,
    name: str,
    description: str,
    agent_type: str,
    greeting: str,
    tone: str,
    response_style: str,
    business_description: str,
    booking_rules: str | None = None,
    pricing_disclosure_policy: str | None = None,
    handoff_rules_text: str | None = None,
    restricted_topics: list[str] | None = None,
    custom_instructions: str | None = None,
    enabled_tools: dict[str, bool] | None = None,
    example_questions: list[str] | None = None,
    suggested_articles: list[SuggestedArticle] | None = None,
    category: str | None = None,
    marketplace_blurb: str | None = None,
    featured: bool = False,
) -> IndustryTemplate:
    return IndustryTemplate(
        key=key,
        name=name,
        description=description,
        agent_type=agent_type,
        greeting=greeting,
        tone=tone,
        response_style=response_style,
        business_description=business_description,
        booking_rules=booking_rules,
        pricing_disclosure_policy=pricing_disclosure_policy
        or "Do not invent prices. Quote only confirmed published rates or schedule a human quote.",
        handoff_rules_text=handoff_rules_text
        or "Transfer for emergencies, billing disputes, legal requests, or when the caller asks for a person.",
        restricted_topics=restricted_topics
        or ["medical diagnosis", "legal advice", "guaranteed outcomes"],
        custom_instructions=custom_instructions,
        enabled_tools=enabled_tools or dict(_ALL_TOOLS),
        example_questions=example_questions or [],
        suggested_articles=suggested_articles or [],
        category=category or _CATEGORY_BY_TYPE.get(agent_type, "General"),
        marketplace_blurb=marketplace_blurb,
        featured=featured,
    )


TEMPLATES: dict[str, IndustryTemplate] = {
    "hvac": _tpl(
        key="hvac",
        name="HVAC",
        description="Heating, cooling, and maintenance reception.",
        marketplace_blurb="Answer service calls, book jobs, and escalate emergencies for HVAC businesses.",
        featured=True,
        agent_type="receptionist",
        greeting="Thanks for calling. How can I help with your heating or cooling today?",
        tone="friendly",
        response_style="concise",
        business_description="Field service HVAC company answering inbound service and booking calls.",
        booking_rules="Confirm address, issue, urgency, and preferred window before booking.",
        example_questions=[
            "My AC is not cooling",
            "Can I book a furnace tune-up?",
            "Do you offer emergency service?",
        ],
        suggested_articles=[
            SuggestedArticle(
                category="faq",
                title="Service area",
                body="We serve the areas listed in our business profile. Confirm the caller's address is in area before booking.",
                tags=["service-area"],
            ),
            SuggestedArticle(
                category="faq",
                title="Emergency guidance",
                body="For gas smells or carbon monoxide alarms, tell the caller to leave the building and contact emergency services, then offer human handoff.",
                tags=["emergency"],
            ),
        ],
    ),
    "medical": _tpl(
        key="medical",
        name="Medical",
        description="Clinic front desk for appointments and general info.",
        marketplace_blurb="Schedule appointments and answer office FAQs without giving clinical advice.",
        featured=True,
        category="Healthcare",
        agent_type="booking",
        greeting="Thank you for calling. I can help with appointments and general office information.",
        tone="professional",
        response_style="concise",
        business_description="Medical office receptionist for scheduling and non-clinical questions.",
        booking_rules="Never give medical advice. Collect reason for visit at a high level only.",
        restricted_topics=[
            "diagnosis",
            "prescription changes",
            "test result interpretation",
        ],
        custom_instructions=(
            "When the caller asks for diagnosis, prescriptions, test results, or "
            "other clinical advice, say you cannot advise on that and offer to "
            "connect them with staff. Do not discuss protected health details "
            "beyond what is needed to schedule. Do not give medical advice."
        ),
        example_questions=[
            "I need to reschedule",
            "What are your hours?",
            "Do you accept new patients?",
        ],
    ),
    "restaurant": _tpl(
        key="restaurant",
        name="Restaurant",
        description="Reservations, hours, and menu questions.",
        marketplace_blurb="Take reservations and answer dining questions around the clock.",
        featured=True,
        category="Hospitality",
        agent_type="booking",
        greeting="Thanks for calling. Looking to reserve a table or ask about tonight?",
        tone="friendly",
        response_style="concise",
        business_description="Restaurant host for reservations and dining questions.",
        booking_rules="Collect party size, date, time, and name. Note allergies if mentioned.",
        enabled_tools={
            "crm": True,
            "scheduling": True,
            "knowledge": True,
            "handoff": True,
            "sms": True,
        },
        example_questions=[
            "Table for four at 7",
            "Are you open Sunday?",
            "Do you have outdoor seating?",
        ],
    ),
    "insurance": _tpl(
        key="insurance",
        name="Insurance",
        description="Policy questions, claims intake, and transfers.",
        marketplace_blurb="Intake quotes and claims, then route sensitive cases to your team.",
        category="Financial services",
        agent_type="support",
        greeting="Thank you for calling. I can help with general policy questions or connect you to the right team.",
        tone="professional",
        response_style="formal",
        business_description="Insurance agency intake for quotes, claims routing, and FAQs.",
        booking_rules=None,
        restricted_topics=["guaranteed coverage decisions", "legal advice"],
        custom_instructions=(
            "Do not bind coverage or promise claim outcomes. For quote or claim "
            "intake, capture the basics the caller provides, then escalate when "
            "they ask to file a claim, dispute a decision, or need a licensed "
            "agent. Do not invent policy terms."
        ),
        enabled_tools={
            "crm": True,
            "scheduling": False,
            "knowledge": True,
            "handoff": True,
            "sms": True,
        },
        example_questions=[
            "I need a quote",
            "How do I start a claim?",
            "What documents do you need?",
        ],
    ),
    "real_estate": _tpl(
        key="real_estate",
        name="Real Estate",
        description="Lead qualification and showing requests.",
        marketplace_blurb="Qualify buyer/seller leads and book showings for your agents.",
        featured=True,
        category="Real estate",
        agent_type="sales",
        greeting="Thanks for calling. Are you looking to buy, sell, or schedule a showing?",
        tone="friendly",
        response_style="sales",
        business_description="Real estate lead intake and appointment coordination.",
        booking_rules="Capture budget range, timeline, and preferred neighborhoods before booking showings.",
        example_questions=[
            "Is this home still available?",
            "Can I tour this weekend?",
            "What is the asking price?",
        ],
    ),
    "call_center": _tpl(
        key="call_center",
        name="Call Center",
        description="General inbound support with escalation paths.",
        marketplace_blurb="Triage inbound support, answer FAQs, and escalate to supervisors.",
        agent_type="call_center",
        greeting="Thanks for calling support. How can I help you today?",
        tone="professional",
        response_style="support",
        business_description="Inbound call center agent for triage, FAQs, and ticket creation.",
        booking_rules=None,
        enabled_tools={
            "crm": True,
            "scheduling": False,
            "knowledge": True,
            "handoff": True,
            "sms": False,
        },
        example_questions=[
            "Where is my order?",
            "I want to speak to a supervisor",
            "I have a billing issue",
        ],
    ),
    "support": _tpl(
        key="support",
        name="Customer Support",
        description="FAQ, troubleshooting, and order help.",
        marketplace_blurb="Handle common support questions and capture issues for follow-up.",
        featured=True,
        agent_type="support",
        greeting="Hi, you've reached support. What can I help you with?",
        tone="friendly",
        response_style="support",
        business_description="Customer support agent for FAQs, troubleshooting, and order status.",
        example_questions=["Reset my password", "Return policy", "Order status"],
    ),
    "sales": _tpl(
        key="sales",
        name="Sales",
        description="Lead qualification and product recommendations.",
        marketplace_blurb="Qualify inbound sales interest and book demos or quote calls.",
        featured=True,
        agent_type="sales",
        greeting="Thanks for calling. Are you exploring options or ready for a quote?",
        tone="friendly",
        response_style="sales",
        business_description="Sales agent for qualification, recommendations, and quote requests.",
        booking_rules="Qualify need, timeline, and budget before booking a sales consult.",
        example_questions=[
            "What plans do you offer?",
            "Can I get a demo?",
            "Who is this a fit for?",
        ],
    ),
    "collections": _tpl(
        key="collections",
        name="Collections",
        description="Polite payment reminders and callback scheduling.",
        marketplace_blurb="Remind customers about balances and schedule callback or payment windows.",
        category="Financial services",
        agent_type="support",
        greeting="Hi, I'm calling about an open balance. Is now a good time to talk?",
        tone="professional",
        response_style="formal",
        business_description="Collections outreach agent for reminders and payment arrangement intake.",
        booking_rules="Never threaten. Capture preferred callback time or payment plan interest and escalate disputes.",
        restricted_topics=["legal threats", "credit score manipulation"],
        custom_instructions=(
            "Be respectful. At the start of the call, confirm identity lightly, "
            "state the reason for the call once, and stop if the caller says it "
            "is a bad time. When the caller disputes the balance, asks for a "
            "person, or becomes distressed, offer handoff. Do not threaten or "
            "repeat the debt reason every turn."
        ),
        enabled_tools={
            "crm": True,
            "scheduling": True,
            "knowledge": True,
            "handoff": True,
            "sms": True,
        },
        example_questions=[
            "How much do I owe?",
            "Can I set up a payment plan?",
            "Please call me later",
        ],
    ),
    "custom": _tpl(
        key="custom",
        name="Custom",
        description="Blank template for fully configurable agents.",
        marketplace_blurb="Start from a blank agent and configure prompts, tools, and flow yourself.",
        agent_type="custom",
        greeting="Thanks for calling. How can I help?",
        tone="professional",
        response_style="concise",
        business_description="Configurable AI employee for this business.",
        example_questions=["What do you do?", "How can you help me?"],
    ),
}


def list_templates() -> list[dict[str, Any]]:
    return [TEMPLATES[k].summarize() for k in sorted(TEMPLATES.keys())]


def list_marketplace_catalog() -> dict[str, Any]:
    templates = list_templates()
    categories = sorted({t["category"] for t in templates})
    featured = [t for t in templates if t.get("featured")]
    return {
        "templates": templates,
        "categories": categories,
        "featured": featured,
    }


def get_template(key: str) -> IndustryTemplate | None:
    return TEMPLATES.get((key or "").strip().lower())
