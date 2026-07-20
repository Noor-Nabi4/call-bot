"""Plan catalog for platform SaaS subscriptions.

Pricing is driven by voice minutes, concurrency, and operational features —
not per-seat primary pricing. Plans are defined here in code; Stripe Checkout
uses inline price_data so Products/Prices do not need to be registered in Stripe.
"""

from __future__ import annotations

from typing import Any

from callbot_platform.domain.enums import PlanKey

# Entitlements enforced / displayed per paid plan.
PLAN_ENTITLEMENTS: dict[str, dict[str, Any]] = {
    PlanKey.STARTER.value: {
        "monthly_minutes": 250,
        "concurrent_calls": 1,
        "phone_numbers": 1,
        "team_users": 3,
        "knowledge_documents": 10,
        "dispatch_enabled": False,
        "tech_mobile_enabled": False,
        "advanced_handoff_enabled": False,
    },
    PlanKey.GROWTH.value: {
        "monthly_minutes": 800,
        "concurrent_calls": 3,
        "phone_numbers": 3,
        "team_users": 10,
        "knowledge_documents": 100,
        "dispatch_enabled": True,
        "tech_mobile_enabled": True,
        "advanced_handoff_enabled": True,
    },
    PlanKey.PRO.value: {
        "monthly_minutes": 2000,
        "concurrent_calls": 10,
        "phone_numbers": 10,
        "team_users": 25,
        "knowledge_documents": 500,
        "dispatch_enabled": True,
        "tech_mobile_enabled": True,
        "advanced_handoff_enabled": True,
    },
}

PLAN_CATALOG: list[dict[str, Any]] = [
    {
        "key": PlanKey.STARTER.value,
        "name": "Starter",
        "tagline": "For small businesses that need every call answered.",
        "cta": "Start with Starter",
        "popular": False,
        "checkoutable": True,
        # List price in cents (USD) — used for Checkout price_data (not Stripe Dashboard Prices).
        "unit_amount": 9900,
        "annual_amount": 99000,
        "currency": "usd",
        "interval": "month",
        "overage_per_minute_cents": 35,
        "highlights": [
            "250 voice minutes / month",
            "1 concurrent call",
            "1 connected phone number",
            "3 team users",
            "10 knowledge documents",
        ],
        "features": [
            "Tenant-specific AI receptionist",
            "250 included voice minutes",
            "One connected or platform-provisioned number",
            "Customer lookup and creation",
            "Appointment booking, rescheduling, and cancellation",
            "Call history and summaries",
            "Basic knowledge base",
            "Basic human transfer",
            "Dashboard metrics",
            "Three team users",
            "Email support",
            "Overage $0.35/min",
        ],
        "entitlements": PLAN_ENTITLEMENTS[PlanKey.STARTER.value],
    },
    {
        "key": PlanKey.GROWTH.value,
        "name": "Growth",
        "tagline": "For service teams managing calls, appointments and field work.",
        "cta": "Choose Growth",
        "popular": True,
        "badge": "Most popular",
        "checkoutable": True,
        "unit_amount": 24900,
        "annual_amount": 249000,
        "currency": "usd",
        "interval": "month",
        "overage_per_minute_cents": 30,
        "highlights": [
            "800 voice minutes / month",
            "3 concurrent calls",
            "Up to 3 phone numbers",
            "10 team users",
            "Dispatch + technician mobile",
        ],
        "features": [
            "Everything in Starter",
            "800 included voice minutes",
            "Three concurrent calls",
            "Up to three phone numbers",
            "Dispatch board",
            "Technician mobile workspace",
            "Job creation and assignment",
            "Warm and cold transfer",
            "Advanced handoff rules",
            "Up to 100 knowledge documents",
            "Calls and booking analytics",
            "Ten team users",
            "Priority support",
            "Overage $0.30/min",
        ],
        "entitlements": PLAN_ENTITLEMENTS[PlanKey.GROWTH.value],
    },
    {
        "key": PlanKey.PRO.value,
        "name": "Pro",
        "tagline": "For established service businesses handling higher call volume.",
        "cta": "Choose Pro",
        "popular": False,
        "checkoutable": True,
        "unit_amount": 49900,
        "annual_amount": 499000,
        "currency": "usd",
        "interval": "month",
        "overage_per_minute_cents": 25,
        "highlights": [
            "2,000 voice minutes / month",
            "10 concurrent calls",
            "Up to 10 phone numbers",
            "25 team users",
            "Extended analytics + priority onboarding",
        ],
        "features": [
            "Everything in Growth",
            "2,000 included voice minutes",
            "Ten concurrent calls",
            "Up to ten phone numbers",
            "Twenty-five team users",
            "Up to 500 knowledge documents",
            "Advanced business and conversation rules",
            "Department or number-based routing",
            "Extended analytics",
            "Priority onboarding",
            "Faster support response",
            "Higher operational limits",
            "Overage $0.25/min",
        ],
        "entitlements": PLAN_ENTITLEMENTS[PlanKey.PRO.value],
    },
]

ENTERPRISE_PLAN: dict[str, Any] = {
    "key": "enterprise",
    "name": "Enterprise",
    "tagline": "For high-volume or multi-location operations.",
    "cta": "Contact sales",
    "popular": False,
    "checkoutable": False,
    "unit_amount": None,
    "annual_amount": None,
    "currency": "usd",
    "interval": None,
    "highlights": [
        "5,000+ monthly minutes",
        "Custom concurrency",
        "Custom number and user limits",
        "Dedicated onboarding + SLA options",
    ],
    "features": [
        "5,000+ monthly minutes",
        "Custom concurrency",
        "Custom number limits",
        "Custom user limits",
        "Dedicated onboarding",
        "Custom integrations",
        "Security review",
        "Priority incident handling",
        "Contract and invoice billing",
        "Optional service-level agreement",
    ],
    "entitlements": None,
}

TRIAL_OFFER: dict[str, Any] = {
    "days": 14,
    "voice_minutes": 50,
    "concurrent_calls": 1,
    "browser_voice_testing": True,
    "credit_card_required": False,
    "summary": (
        "14 days, 50 voice minutes, one concurrent call, "
        "browser voice testing — no credit card required."
    ),
    "phone_number_requirements": [
        "Verified email",
        "Payment method",
        "Business information",
        "Explicit number-purchase confirmation",
    ],
}

NUMBER_PRICING: dict[str, Any] = {
    "connect_existing": {
        "platform_fee": 0,
        "summary": (
            "No additional platform connection fee. "
            "You pay your own Twilio number and carrier charges."
        ),
    },
    "platform_purchase": {
        "us_local_monthly_cents": 500,
        "summary": (
            "US local number $5/month. Carrier usage is included in billed "
            "voice minutes. Additional regulatory charges may apply."
        ),
    },
}

ADD_ONS: list[dict[str, Any]] = [
    {
        "key": "extra_user",
        "name": "Extra user",
        "unit_amount": 1200,
        "interval": "month",
        "currency": "usd",
    },
    {
        "key": "extra_phone_number",
        "name": "Extra phone number",
        "unit_amount": 500,
        "interval": "month",
        "currency": "usd",
    },
    {
        "key": "minutes_bundle_500",
        "name": "Additional 500-minute bundle",
        "unit_amount": 12500,
        "interval": "month",
        "currency": "usd",
    },
    {
        "key": "assisted_onboarding",
        "name": "Assisted onboarding",
        "unit_amount": 29900,
        "interval": "one_time",
        "currency": "usd",
    },
    {
        "key": "custom_integration",
        "name": "Custom integration",
        "unit_amount": None,
        "interval": None,
        "currency": "usd",
        "summary": "Quoted separately",
    },
    {
        "key": "sms_usage",
        "name": "SMS usage",
        "unit_amount": None,
        "interval": None,
        "currency": "usd",
        "summary": "Charged separately",
    },
]

VALID_PLAN_KEYS = frozenset(p["key"] for p in PLAN_CATALOG)

# Subscription statuses that unlock ops features.
ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"trialing", "active"})

# Statuses that may start a new Checkout Session.
CHECKOUT_ELIGIBLE_STATUSES = frozenset(
    {"incomplete", "incomplete_expired", "canceled", "unpaid"}
)


def entitlements_for_plan(plan_key: str) -> dict[str, Any] | None:
    return PLAN_ENTITLEMENTS.get(plan_key.strip().lower())


def plan_by_key(plan_key: str) -> dict[str, Any] | None:
    key = plan_key.strip().lower()
    for plan in PLAN_CATALOG:
        if plan["key"] == key:
            return plan
    return None


def public_plans() -> list[dict[str, Any]]:
    """Return the checkoutable plan catalog (always ready — no Stripe Price setup)."""
    return [{**plan, "configured": True} for plan in PLAN_CATALOG]


def pricing_meta() -> dict[str, Any]:
    """Non-checkout pricing surfaces for the marketing site."""
    return {
        "enterprise": ENTERPRISE_PLAN,
        "trial": TRIAL_OFFER,
        "number_pricing": NUMBER_PRICING,
        "add_ons": ADD_ONS,
        "pricing_model": (
            "Voice minutes, concurrent calls, and operational features. "
            "Per-user pricing is secondary via add-ons."
        ),
    }
