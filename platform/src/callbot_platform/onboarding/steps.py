"""Canonical onboarding step registry (extensible for later Phase 2 tasks)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OnboardingStepDef:
    key: str
    title: str
    required: bool
    description: str = ""


# Ordered registry. Future tasks may filter/extend via industry/business-model
# without changing persistence — only applicability of steps.
ONBOARDING_STEPS: tuple[OnboardingStepDef, ...] = (
    OnboardingStepDef(
        key="business_profile",
        title="Business profile",
        required=True,
        description="Name, contact, timezone, and location",
    ),
    OnboardingStepDef(
        key="industry",
        title="Industry",
        required=True,
        description="Primary industry for templates and defaults",
    ),
    OnboardingStepDef(
        key="business_model",
        title="Business model",
        required=True,
        description="How the business sells (products, services, appointments, …)",
    ),
    OnboardingStepDef(
        key="catalog",
        title="Products & services",
        required=False,
        description="Optional catalog setup (commerce ships later)",
    ),
    OnboardingStepDef(
        key="customers",
        title="Customers",
        required=False,
        description="Optional CRM starter configuration",
    ),
    OnboardingStepDef(
        key="business_hours",
        title="Business hours",
        required=True,
        description="Schedule and availability defaults",
    ),
    OnboardingStepDef(
        key="team",
        title="Team",
        required=False,
        description="Invite members (optional during first run)",
    ),
    OnboardingStepDef(
        key="ai_configuration",
        title="AI agent",
        required=False,
        description="Voice agent profile and tools (optional during first run)",
    ),
    OnboardingStepDef(
        key="knowledge",
        title="Knowledge",
        required=False,
        description="FAQ / knowledge base (optional)",
    ),
    OnboardingStepDef(
        key="phone_setup",
        title="Phone setup",
        required=True,
        description="At least one verified inbound phone number",
    ),
    OnboardingStepDef(
        key="review",
        title="Review",
        required=True,
        description="Confirm configuration before going live",
    ),
)

STEP_BY_KEY: dict[str, OnboardingStepDef] = {s.key: s for s in ONBOARDING_STEPS}
STEP_ORDER: tuple[str, ...] = tuple(s.key for s in ONBOARDING_STEPS)
REQUIRED_STEPS: frozenset[str] = frozenset(
    s.key for s in ONBOARDING_STEPS if s.required
)
OPTIONAL_STEPS: frozenset[str] = frozenset(
    s.key for s in ONBOARDING_STEPS if not s.required
)


def known_step(key: str) -> bool:
    return key in STEP_BY_KEY


def is_required(key: str) -> bool:
    step = STEP_BY_KEY.get(key)
    return bool(step and step.required)


def list_step_defs() -> list[dict[str, object]]:
    return [
        {
            "key": s.key,
            "title": s.title,
            "required": s.required,
            "description": s.description,
        }
        for s in ONBOARDING_STEPS
    ]
