"""Authoritative operational data — must come from tools/domain services.

The LLM may explain tool results. It must never invent these values.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class AuthoritativeData(StrEnum):
    PRICE = "PRICE"
    INVENTORY = "INVENTORY"
    AVAILABILITY = "AVAILABILITY"
    TECHNICIAN = "TECHNICIAN"
    CUSTOMER_HISTORY = "CUSTOMER_HISTORY"
    ORDER_STATUS = "ORDER_STATUS"
    PAYMENT_STATUS = "PAYMENT_STATUS"


# tool_name → authoritative categories that tool may return as source of truth
AUTHORITATIVE_TOOL_MAP: dict[str, tuple[AuthoritativeData, ...]] = {
    "get_product_price": (AuthoritativeData.PRICE,),
    "get_service_price": (AuthoritativeData.PRICE,),
    "search_products": (AuthoritativeData.PRICE,),
    "get_product": (AuthoritativeData.PRICE,),
    "check_inventory": (AuthoritativeData.INVENTORY,),
    "check_availability": (
        AuthoritativeData.AVAILABILITY,
        AuthoritativeData.TECHNICIAN,
    ),
    "create_booking": (
        AuthoritativeData.AVAILABILITY,
        AuthoritativeData.TECHNICIAN,
    ),
    "create_appointment": (
        AuthoritativeData.AVAILABILITY,
        AuthoritativeData.TECHNICIAN,
    ),
    "reschedule_appointment": (
        AuthoritativeData.AVAILABILITY,
        AuthoritativeData.TECHNICIAN,
    ),
    "get_customer_context": (AuthoritativeData.CUSTOMER_HISTORY,),
    "find_customer": (AuthoritativeData.CUSTOMER_HISTORY,),
    "find_orders": (AuthoritativeData.ORDER_STATUS,),
    "get_order_status": (AuthoritativeData.ORDER_STATUS,),
    "get_payment_status": (AuthoritativeData.PAYMENT_STATUS,),
    "create_payment_link": (AuthoritativeData.PAYMENT_STATUS, AuthoritativeData.PRICE),
}

# Model-supplied fields that must never override domain-computed authoritative values.
# Overlaps Phase 14 FORBIDDEN_ARG_KEYS — kept as the guardrail catalog source.
AUTHORITATIVE_INJECTION_KEYS: frozenset[str] = frozenset(
    {
        "unit_price",
        "unitPrice",
        "subtotal",
        "tax",
        "total",
        "discount",
        "currency",
        "inventory_balance",
        "inventoryBalance",
        "appointment_status",
        "appointmentStatus",
        "order_status",
        "orderStatus",
        "job_status",
        "jobStatus",
        "payment_status",
        "paymentStatus",
        "price",
        "inventory",
        "quantity_available",
        "quantityAvailable",
        "technician_name",
        "technicianName",
        "assigned_technician_id",
        "assignedTechnicianId",
    }
)


def list_authoritative_categories() -> list[dict[str, Any]]:
    return [
        {
            "key": item.value,
            "tools": [
                tool for tool, cats in AUTHORITATIVE_TOOL_MAP.items() if item in cats
            ],
        }
        for item in AuthoritativeData
    ]


def tools_for_category(category: AuthoritativeData | str) -> tuple[str, ...]:
    key = AuthoritativeData(category)
    return tuple(tool for tool, cats in AUTHORITATIVE_TOOL_MAP.items() if key in cats)


def is_authoritative_injection_key(key: str) -> bool:
    return key in AUTHORITATIVE_INJECTION_KEYS
