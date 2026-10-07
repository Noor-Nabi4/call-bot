"""SMS agent constants — intents, tools, statuses."""

from __future__ import annotations

# Tools the SMS channel may invoke via AIToolExecutor (Phase 14 registry).
SMS_ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "find_customer",
        "get_customer_context",
        "search_services",
        "get_service_price",
        "check_availability",
        "create_booking",
        "reschedule_appointment",
        "cancel_appointment",
        "search_products",
        "get_product",
        "get_product_price",
        "check_inventory",
        "find_orders",
        "get_order_status",
        "create_customer",
        "send_sms",
        "request_human",
        "search_knowledge",
        "create_payment_link",
        "send_payment_link_sms",
        "send_payment_link_email",
        "get_payment_status",
    }
)

INTENTS: frozenset[str] = frozenset(
    {
        "GENERAL_QUESTION",
        "BOOKING",
        "RESCHEDULE",
        "CANCELLATION",
        "ORDER_STATUS",
        "PRODUCT_QUESTION",
        "AVAILABILITY",
        "PRICE",
        "HUMAN_HANDOFF",
        "UNKNOWN",
        "CONFIRMATION",
        "SLOT_SELECTION",
    }
)

DEFAULT_CONTEXT_MESSAGES = 20
MAX_BODY_CHARS = 1600
MAX_OUTBOUND_CHARS = 480
