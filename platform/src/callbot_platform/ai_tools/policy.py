"""Timeout classes, retry safety, and customer-safe error copy."""

from __future__ import annotations

from enum import StrEnum

from callbot_platform.ai_tools.types import ERROR_CODES


class TimeoutClass(StrEnum):
    FAST_READ = "FAST_READ"
    STANDARD_READ = "STANDARD_READ"
    AVAILABILITY = "AVAILABILITY"
    MUTATION = "MUTATION"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"


# Bounded wall-clock budgets for AI tool handlers (seconds).
# Chosen for voice latency: reads stay under a turn; mutations under a short pause.
TIMEOUT_SECONDS: dict[TimeoutClass, float] = {
    TimeoutClass.FAST_READ: 2.0,
    TimeoutClass.STANDARD_READ: 4.0,
    TimeoutClass.AVAILABILITY: 6.0,
    TimeoutClass.MUTATION: 8.0,
    TimeoutClass.EXTERNAL_PROVIDER: 10.0,
}

# Client-side read retries (same args). Mutations retry only with stable operation_id.
MAX_READ_ATTEMPTS = 2
MAX_MUTATION_ATTEMPTS = 2

# Never auto-retry these codes (client or executor).
NON_RETRYABLE_CODES: frozenset[str] = frozenset(
    {
        "invalid_arguments",
        "permission_denied",
        "tenant_access_denied",
        "not_found",
        "ambiguous_result",
        "customer_not_found",
        "customer_already_exists",
        "service_not_found",
        "product_not_found",
        "variant_not_found",
        "inventory_unavailable",
        "price_unavailable",
        "availability_empty",
        "booking_conflict",
        "booking_invalid",
        "order_conflict",
        "order_invalid",
        "idempotency_conflict",
        "operation_already_completed",
        "confirmation_required",
        "expired",
        "archived",
        "handoff_unavailable",
    }
)

CUSTOMER_SAFE_MESSAGES: dict[str, str] = {
    "invalid_arguments": "I need a bit more information to continue.",
    "permission_denied": "I can't complete that request.",
    "tenant_access_denied": "I can't complete that request.",
    "not_found": "I couldn't find that record.",
    "ambiguous_result": "I found more than one match — can you clarify?",
    "customer_not_found": "I couldn't find that customer on file.",
    "customer_already_exists": "That customer is already on file.",
    "service_not_found": "I couldn't find that service.",
    "product_not_found": "I couldn't find that product.",
    "variant_not_found": "I couldn't find that product option.",
    "inventory_unavailable": "That item isn't available right now.",
    "price_unavailable": "I don't have a price for that right now.",
    "availability_empty": "I don't see an opening that matches those times.",
    "booking_conflict": "The selected time is no longer available.",
    "booking_invalid": "That appointment time isn't valid.",
    "order_conflict": "I couldn't complete that order — please try again.",
    "order_invalid": "I couldn't place that order with those details.",
    "idempotency_conflict": "That request conflicts with an earlier one.",
    "operation_already_completed": "That request was already completed.",
    "confirmation_required": "Please confirm the details with the caller first.",
    "expired": "That information is no longer valid.",
    "archived": "That record is no longer active.",
    "system_unavailable": ("I'm sorry, I wasn't able to complete that right now."),
    "provider_unavailable": ("I'm sorry, I wasn't able to complete that right now."),
    "handoff_unavailable": ("I wasn't able to connect you with a teammate right now."),
}


def customer_safe_message(code: str) -> str:
    if code in CUSTOMER_SAFE_MESSAGES:
        return CUSTOMER_SAFE_MESSAGES[code]
    if code in ERROR_CODES:
        return CUSTOMER_SAFE_MESSAGES["system_unavailable"]
    return CUSTOMER_SAFE_MESSAGES["system_unavailable"]


def is_retryable_code(code: str | None) -> bool:
    if not code:
        return True
    return code not in NON_RETRYABLE_CODES
