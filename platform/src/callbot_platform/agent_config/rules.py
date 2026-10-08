"""Transfer, escalation, and after-hours rule catalogs."""

from __future__ import annotations

from typing import Any

TRANSFER_RULE_KEYS: tuple[str, ...] = (
    "customer_requests_human",
    "customer_frustrated",
    "ai_cannot_answer",
    "high_priority_customer",
    "emergency_request",
    "billing_issue",
)

ESCALATION_RULE_KEYS: tuple[str, ...] = (
    "customer_requests_human",
    "ai_cannot_resolve",
    "repeated_failed_attempts",
    "high_value_lead",
    "emergency_intent",
    "sensitive_billing",
)

# Deterministic precedence (highest first).
ESCALATION_PRIORITY: tuple[str, ...] = (
    "emergency_intent",
    "customer_requests_human",
    "sensitive_billing",
    "high_value_lead",
    "repeated_failed_attempts",
    "ai_cannot_resolve",
)

AFTER_HOURS_BEHAVIORS: frozenset[str] = frozenset(
    {
        "take_message",
        "offer_callback",
        "transfer_emergency",
        "after_hours_message",
    }
)
DEFAULT_AFTER_HOURS = "take_message"


def default_transfer_rules() -> dict[str, bool]:
    return {
        "customer_requests_human": True,
        "customer_frustrated": True,
        "ai_cannot_answer": True,
        "high_priority_customer": False,
        "emergency_request": True,
        "billing_issue": True,
    }


def default_escalation_rules() -> dict[str, bool]:
    return {
        "customer_requests_human": True,
        "ai_cannot_resolve": True,
        "repeated_failed_attempts": True,
        "high_value_lead": False,
        "emergency_intent": True,
        "sensitive_billing": True,
    }


def normalize_bool_rules(
    raw: dict[str, Any] | None, *, allowed: tuple[str, ...], defaults: dict[str, bool]
) -> dict[str, bool]:
    out = dict(defaults)
    if not raw:
        return out
    for key in allowed:
        if key in raw:
            out[key] = bool(raw[key])
    return out


def normalize_after_hours(raw: str | None) -> str:
    key = (raw or DEFAULT_AFTER_HOURS).strip().lower()
    return key if key in AFTER_HOURS_BEHAVIORS else DEFAULT_AFTER_HOURS


def list_rule_catalogs() -> dict[str, Any]:
    return {
        "transfer_rules": [
            {
                "key": k,
                "display_name": k.replace("_", " ").title(),
            }
            for k in TRANSFER_RULE_KEYS
        ],
        "escalation_rules": [
            {
                "key": k,
                "display_name": k.replace("_", " ").title(),
            }
            for k in ESCALATION_RULE_KEYS
        ],
        "escalation_priority": list(ESCALATION_PRIORITY),
        "after_hours_behaviors": [
            {"key": "take_message", "display_name": "Take a message"},
            {"key": "offer_callback", "display_name": "Offer callback"},
            {"key": "transfer_emergency", "display_name": "Transfer to emergency line"},
            {"key": "after_hours_message", "display_name": "Play after-hours message"},
        ],
    }
