"""Shared AI tool context and structured result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar
from uuid import UUID

T = TypeVar("T")

ACTOR_AI_VOICE = "AI_VOICE_AGENT"
ACTOR_AI_SMS = "AI_SMS_AGENT"

# Canonical structured error codes (customer-safe messaging is separate).
ERROR_CODES: frozenset[str] = frozenset(
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
        "system_unavailable",
        "provider_unavailable",
        "handoff_unavailable",
    }
)

# Never accept these as model-controlled arguments.
FORBIDDEN_ARG_KEYS: frozenset[str] = frozenset(
    {
        "tenant_id",
        "tenantId",
        "organization_id",
        "organizationId",
        "actor_id",
        "actorId",
        "permissions",
        "role",
        "created_by",
        "createdBy",
        "updated_by",
        "updatedBy",
        "audit_actor",
        "auditActor",
        "unit_price",
        "unitPrice",
        "subtotal",
        "tax",
        "total",
        "inventory_balance",
        "inventoryBalance",
        "appointment_status",
        "appointmentStatus",
        "order_status",
        "orderStatus",
        "job_status",
        "jobStatus",
        "estimate_status",
        "estimateStatus",
        "assigned_technician_id",
        "assignedTechnicianId",
        "status",  # status mutations are server-controlled unless tool allows
        "org_id",
        "orgId",
        "user_id",
        "userId",
        "roleName",
        "role_name",
        "admin",
        "isAdmin",
        "is_admin",
        "raw_sql",
        "rawSql",
        "table_name",
        "tableName",
        "repository",
        "discount",
        "currency",
    }
)

# Tools that may accept a controlled status filter (read-only).
STATUS_FILTER_ALLOWED: frozenset[str] = frozenset(
    {
        "find_orders",
        "find_estimates",
    }
)


@dataclass(frozen=True, slots=True)
class AIToolContext:
    """Trusted context — never taken from model-generated tool arguments."""

    tenant_id: UUID
    call_id: UUID | None
    actor_type: str = ACTOR_AI_VOICE
    operation_id: UUID | None = None
    customer_id: UUID | None = None
    caller_phone: str | None = None
    confirmed: bool = False
    conversation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AIToolError:
    code: str
    retryable: bool
    customer_safe: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "retryable": self.retryable,
            "customerSafe": self.customer_safe,
        }


@dataclass(frozen=True, slots=True)
class AIToolResult(Generic[T]):
    ok: bool
    data: T | None = None
    error: AIToolError | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok}
        if self.data is not None:
            out["data"] = self.data
        if self.error is not None:
            out["error"] = self.error.to_dict()
        return out


def ok_result(data: Any) -> AIToolResult[Any]:
    return AIToolResult(ok=True, data=data)


def err_result(
    code: str,
    *,
    retryable: bool = False,
    customer_safe: bool = True,
) -> AIToolResult[Any]:
    normalized = code if code in ERROR_CODES else "system_unavailable"
    return AIToolResult(
        ok=False,
        error=AIToolError(
            code=normalized,
            retryable=retryable,
            customer_safe=customer_safe,
        ),
    )


# Default retryable / customerSafe hints for known codes.
_ERROR_META: dict[str, tuple[bool, bool]] = {
    "invalid_arguments": (False, True),
    "permission_denied": (False, True),
    "tenant_access_denied": (False, True),
    "not_found": (False, True),
    "ambiguous_result": (False, True),
    "customer_not_found": (False, True),
    "customer_already_exists": (False, True),
    "service_not_found": (False, True),
    "product_not_found": (False, True),
    "variant_not_found": (False, True),
    "inventory_unavailable": (False, True),
    "price_unavailable": (False, True),
    "availability_empty": (False, True),
    "booking_conflict": (True, True),
    "booking_invalid": (False, True),
    "order_conflict": (True, True),
    "order_invalid": (False, True),
    "idempotency_conflict": (False, True),
    "operation_already_completed": (False, True),
    "confirmation_required": (False, True),
    "expired": (False, True),
    "archived": (False, True),
    "system_unavailable": (True, True),
    "provider_unavailable": (True, True),
    "handoff_unavailable": (False, True),
}


def tool_error(code: str) -> AIToolResult[Any]:
    retryable, customer_safe = _ERROR_META.get(code, (False, True))
    return err_result(code, retryable=retryable, customer_safe=customer_safe)
