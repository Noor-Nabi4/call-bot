"""Confirmation-required operation classification — wraps Phase 14 TOOL_SPECS.

Do not create a second confirmation framework. This registry documents and
groups existing ``confirmation_required`` tools for UI/docs/tests.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from callbot_platform.ai_tools.registry import TOOL_SPECS, get_tool_spec


class ConfirmationOperation(StrEnum):
    BOOKING = "BOOKING"
    CANCELLATION = "CANCELLATION"
    RESCHEDULE = "RESCHEDULE"
    ORDER_PLACEMENT = "ORDER_PLACEMENT"
    PAYMENT_ACTION = "PAYMENT_ACTION"
    DESTRUCTIVE_CHANGE = "DESTRUCTIVE_CHANGE"
    SENSITIVE_MUTATION = "SENSITIVE_MUTATION"


# tool_name → operation class (for summaries / UI). Source of truth for
# whether confirmation is required remains ToolSpec.confirmation_required.
OPERATION_BY_TOOL: dict[str, ConfirmationOperation] = {
    "create_booking": ConfirmationOperation.BOOKING,
    "create_appointment": ConfirmationOperation.BOOKING,
    "cancel_appointment": ConfirmationOperation.CANCELLATION,
    "reschedule_appointment": ConfirmationOperation.RESCHEDULE,
    "create_order": ConfirmationOperation.ORDER_PLACEMENT,
    "create_payment_link": ConfirmationOperation.PAYMENT_ACTION,
    "send_payment_link_sms": ConfirmationOperation.PAYMENT_ACTION,
    "send_payment_link_email": ConfirmationOperation.PAYMENT_ACTION,
    "cancel_membership": ConfirmationOperation.DESTRUCTIVE_CHANGE,
    "subscribe_membership": ConfirmationOperation.SENSITIVE_MUTATION,
    "upgrade_membership": ConfirmationOperation.SENSITIVE_MUTATION,
    "downgrade_membership": ConfirmationOperation.SENSITIVE_MUTATION,
    "create_customer": ConfirmationOperation.SENSITIVE_MUTATION,
    "update_customer": ConfirmationOperation.SENSITIVE_MUTATION,
    "create_job": ConfirmationOperation.SENSITIVE_MUTATION,
    "send_sms": ConfirmationOperation.SENSITIVE_MUTATION,
}


def confirmation_required_for_tool(tool_name: str) -> bool:
    spec = get_tool_spec(tool_name)
    if spec is None:
        return True  # unknown tools: fail closed
    return bool(spec.confirmation_required)


def operation_for_tool(tool_name: str) -> ConfirmationOperation | None:
    return OPERATION_BY_TOOL.get(tool_name)


def list_confirmation_required_tools() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, spec in sorted(TOOL_SPECS.items()):
        if not spec.confirmation_required:
            continue
        op = OPERATION_BY_TOOL.get(name)
        out.append(
            {
                "tool": name,
                "operation": op.value
                if op
                else ConfirmationOperation.SENSITIVE_MUTATION.value,
                "tool_group": spec.tool_group,
                "mutation": spec.mutation,
                "idempotency_required": spec.idempotency_required,
            }
        )
    return out


def assert_minimum_confirmation_coverage() -> None:
    """Raise AssertionError if critical ops lose confirmation (test helper)."""
    required = {
        "create_booking",
        "create_appointment",
        "cancel_appointment",
        "reschedule_appointment",
        "create_order",
        "create_payment_link",
        "send_payment_link_sms",
        "send_payment_link_email",
        "cancel_membership",
        "create_customer",
        "update_customer",
        "send_sms",
    }
    missing = [
        name
        for name in required
        if name not in TOOL_SPECS or not TOOL_SPECS[name].confirmation_required
    ]
    if missing:
        raise AssertionError(
            f"Confirmation required tools missing confirmation flag: {missing}"
        )
