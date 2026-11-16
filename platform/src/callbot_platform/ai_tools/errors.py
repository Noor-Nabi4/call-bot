"""Map domain exceptions to structured AI tool errors."""

from __future__ import annotations

from callbot_platform.ai_tools.types import AIToolResult, tool_error
from callbot_platform.crm.errors import CrmError
from callbot_platform.domain.phone import PhoneNumberError
from callbot_platform.rbac.errors import RbacError

_CRM_CODE_MAP: dict[str, str] = {
    "not_found": "not_found",
    "customer_not_found": "customer_not_found",
    "phone_conflict": "customer_already_exists",
    "service_not_found": "service_not_found",
    "service_required": "invalid_arguments",
    "product_not_found": "product_not_found",
    "variant_not_found": "variant_not_found",
    "idempotency_conflict": "idempotency_conflict",
    "booking_conflict": "booking_conflict",
    "slot_conflict": "booking_conflict",
    "conflict": "booking_conflict",
    "appointment_conflict": "booking_conflict",
    "invalid_range": "invalid_arguments",
    "invalid_priority": "invalid_arguments",
    "invalid_status": "invalid_arguments",
    "invalid_schedule": "booking_invalid",
    "invalid_name": "invalid_arguments",
    "items_required": "order_invalid",
    "product_required": "order_invalid",
    "insufficient_inventory": "inventory_unavailable",
    "inventory_unavailable": "inventory_unavailable",
    "price_unavailable": "price_unavailable",
    "archived": "archived",
    "job_archived": "archived",
    "order_archived": "archived",
    "estimate_archived": "archived",
    "location_not_found": "not_found",
    "technician_not_found": "not_found",
    "tenant_not_found": "tenant_access_denied",
}


def map_exception(exc: BaseException) -> AIToolResult:
    if isinstance(exc, RbacError):
        if exc.code == "permission_denied":
            return tool_error("permission_denied")
        return tool_error("invalid_arguments")
    if isinstance(exc, PhoneNumberError):
        return tool_error("invalid_arguments")
    if isinstance(exc, CrmError):
        mapped = _CRM_CODE_MAP.get(exc.code)
        if mapped:
            return tool_error(mapped)
        if "conflict" in exc.code:
            return tool_error("booking_conflict")
        if "invalid" in exc.code:
            return tool_error("invalid_arguments")
        return tool_error("system_unavailable")
    return tool_error("system_unavailable")
