"""Phase 30 capability registry — maps owner toggles to tools + CRM modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CapabilityDef:
    key: str
    display_name: str
    description: str
    risk_level: str  # low | medium | high
    category: str
    tool_names: tuple[str, ...]
    tool_group: str | None
    required_modules: tuple[str, ...]
    default_enabled: bool = True


CAPABILITIES: tuple[CapabilityDef, ...] = (
    CapabilityDef(
        key="CALL_ANSWERING",
        display_name="Answer calls",
        description="Greet callers and answer business questions",
        risk_level="low",
        category="customer_calls",
        tool_names=(),
        tool_group=None,
        required_modules=(),
        default_enabled=True,
    ),
    CapabilityDef(
        key="HUMAN_TRANSFER",
        display_name="Human transfer",
        description="Transfer or queue a human agent via existing handoff",
        risk_level="high",
        category="customer_calls",
        tool_names=("request_human",),
        tool_group="handoff",
        required_modules=(),
        default_enabled=True,
    ),
    CapabilityDef(
        key="APPOINTMENT_BOOK",
        display_name="Book appointments",
        description="Check availability and create bookings",
        risk_level="medium",
        category="scheduling",
        tool_names=("create_booking", "create_appointment", "check_availability"),
        tool_group="scheduling",
        required_modules=("APPOINTMENTS",),
        default_enabled=True,
    ),
    CapabilityDef(
        key="APPOINTMENT_RESCHEDULE",
        display_name="Reschedule",
        description="Reschedule existing appointments",
        risk_level="medium",
        category="scheduling",
        tool_names=("reschedule_appointment",),
        tool_group="scheduling",
        required_modules=("APPOINTMENTS",),
        default_enabled=True,
    ),
    CapabilityDef(
        key="APPOINTMENT_CANCEL",
        display_name="Cancel appointments",
        description="Cancel appointments (confirmation required)",
        risk_level="high",
        category="scheduling",
        tool_names=("cancel_appointment",),
        tool_group="scheduling",
        required_modules=("APPOINTMENTS",),
        default_enabled=False,
    ),
    CapabilityDef(
        key="PRODUCT_SEARCH",
        display_name="Product search",
        description="Search the product catalog",
        risk_level="low",
        category="commerce",
        tool_names=("search_products", "get_product"),
        tool_group="crm",
        required_modules=("PRODUCTS",),
        default_enabled=False,
    ),
    CapabilityDef(
        key="INVENTORY_LOOKUP",
        display_name="Inventory lookup",
        description="Check stock availability",
        risk_level="low",
        category="commerce",
        tool_names=("check_inventory",),
        tool_group="crm",
        required_modules=("INVENTORY",),
        default_enabled=False,
    ),
    CapabilityDef(
        key="PRICING_LOOKUP",
        display_name="Pricing",
        description="Look up product or service prices",
        risk_level="low",
        category="commerce",
        tool_names=("get_product_price", "get_service_price"),
        tool_group="crm",
        required_modules=(),
        default_enabled=True,
    ),
    CapabilityDef(
        key="LEAD_CREATE",
        display_name="Lead creation",
        description="Capture new leads / customers",
        risk_level="medium",
        category="crm",
        tool_names=("create_customer",),
        tool_group="crm",
        required_modules=("CUSTOMERS",),
        default_enabled=True,
    ),
    CapabilityDef(
        key="LEAD_QUALIFY",
        display_name="Lead qualification",
        description="Collect qualification details for leads",
        risk_level="medium",
        category="crm",
        tool_names=("create_job", "get_customer_context"),
        tool_group="crm",
        required_modules=("LEADS", "CUSTOMERS"),
        default_enabled=True,
    ),
    CapabilityDef(
        key="ORDER_LOOKUP",
        display_name="Order lookup",
        description="Find orders and status for a customer",
        risk_level="low",
        category="commerce",
        tool_names=("find_orders", "get_order_status"),
        tool_group="crm",
        required_modules=("ORDERS",),
        default_enabled=False,
    ),
    CapabilityDef(
        key="PAYMENT_LINK",
        display_name="Payment links",
        description="Generate Stripe Checkout links (never card data)",
        risk_level="high",
        category="payments",
        tool_names=(
            "create_payment_link",
            "create_payment_link_for_invoice",
            "get_payment_status",
        ),
        tool_group="payments",
        required_modules=("PAYMENTS",),
        default_enabled=False,
    ),
    CapabilityDef(
        key="SMS_SEND",
        display_name="SMS",
        description="Send SMS via existing notification pipeline",
        risk_level="medium",
        category="messaging",
        tool_names=("send_sms",),
        tool_group="sms",
        required_modules=(),
        default_enabled=True,
    ),
)

CAPABILITY_BY_KEY: dict[str, CapabilityDef] = {c.key: c for c in CAPABILITIES}
CAPABILITY_KEYS: frozenset[str] = frozenset(CAPABILITY_BY_KEY)

# tool_name → capability key (first match wins for enforcement)
TOOL_TO_CAPABILITY: dict[str, str] = {}
for _cap in CAPABILITIES:
    for _tool in _cap.tool_names:
        TOOL_TO_CAPABILITY.setdefault(_tool, _cap.key)

# Map legacy enabled_tools groups → default capabilities when profile has no
# explicit capabilities blob yet.
GROUP_TO_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "crm": (
        "CALL_ANSWERING",
        "LEAD_CREATE",
        "LEAD_QUALIFY",
        "PRODUCT_SEARCH",
        "INVENTORY_LOOKUP",
        "PRICING_LOOKUP",
        "ORDER_LOOKUP",
    ),
    "scheduling": (
        "APPOINTMENT_BOOK",
        "APPOINTMENT_RESCHEDULE",
        "APPOINTMENT_CANCEL",
    ),
    "knowledge": ("CALL_ANSWERING",),
    "handoff": ("HUMAN_TRANSFER",),
    "sms": ("SMS_SEND",),
    "payments": ("PAYMENT_LINK",),
}


def list_capabilities() -> list[dict[str, Any]]:
    return [
        {
            "key": c.key,
            "display_name": c.display_name,
            "description": c.description,
            "risk_level": c.risk_level,
            "category": c.category,
            "tool_names": list(c.tool_names),
            "tool_group": c.tool_group,
            "required_modules": list(c.required_modules),
            "default_enabled": c.default_enabled,
        }
        for c in CAPABILITIES
    ]


def default_capabilities() -> dict[str, bool]:
    return {c.key: c.default_enabled for c in CAPABILITIES}


def capabilities_from_enabled_tools(
    enabled_tools: dict[str, Any] | None,
) -> dict[str, bool]:
    """Derive capability flags from legacy tool-group toggles."""
    tools = enabled_tools or {}
    out = default_capabilities()
    # Start from defaults, then disable groups that are off.
    for group, caps in GROUP_TO_CAPABILITIES.items():
        group_on = bool(
            tools.get(
                group, group in {"crm", "scheduling", "knowledge", "handoff", "sms"}
            )
        )
        for key in caps:
            if not group_on:
                out[key] = False
            elif key in {
                "APPOINTMENT_CANCEL",
                "PAYMENT_LINK",
                "PRODUCT_SEARCH",
                "INVENTORY_LOOKUP",
                "ORDER_LOOKUP",
            }:
                # Keep conservative defaults for high/commerce caps.
                out[key] = CAPABILITY_BY_KEY[key].default_enabled and group_on
            else:
                out[key] = group_on
    out["CALL_ANSWERING"] = True
    return out


def sync_enabled_tools_from_capabilities(
    capabilities: dict[str, bool],
) -> dict[str, bool]:
    """Project fine-grained capabilities back onto tool-group flags."""
    groups = {
        "crm": False,
        "scheduling": False,
        "knowledge": True,
        "handoff": False,
        "sms": False,
        "payments": False,
    }
    for key, enabled in capabilities.items():
        if not enabled:
            continue
        cap = CAPABILITY_BY_KEY.get(key)
        if cap is None:
            continue
        if cap.tool_group:
            groups[cap.tool_group] = True
        if key == "CALL_ANSWERING":
            groups["knowledge"] = True
    return groups


def normalize_capabilities(raw: dict[str, Any] | None) -> dict[str, bool]:
    base = default_capabilities()
    if not raw:
        return base
    for key, value in raw.items():
        ukey = str(key).strip().upper()
        if ukey in CAPABILITY_KEYS:
            base[ukey] = bool(value)
    return base
