"""Declarative allow-listed condition evaluation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.automations.constants import CONDITION_FIELDS, ConditionOperator
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Customer
from callbot_platform.db.models.automations import AutomationEvent
from callbot_platform.db.models.estimates import Estimate
from callbot_platform.db.models.invoices import Invoice
from callbot_platform.db.models.jobs import Job
from callbot_platform.db.models.orders import Order
from callbot_platform.db.models.payments import Payment
from callbot_platform.db.models.scheduling import Appointment


class ConditionError(CrmError):
    pass


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _resolve_field(
    session: Session,
    *,
    tenant_id: UUID,
    event: AutomationEvent,
    path: str,
) -> Any:
    if path not in CONDITION_FIELDS:
        raise ConditionError("invalid_condition_field", f"Unknown field: {path}")

    payload = event.payload or {}
    if path == "event.type":
        return event.event_type
    if path == "event.entity_type":
        return event.entity_type

    # Prefer authoritative DB lookups for financial/operational fields.
    if path.startswith("job."):
        job_id = payload.get("job_id") or (
            event.entity_id if event.entity_type == "job" else None
        )
        if not job_id:
            return None
        job = session.scalar(
            select(Job).where(Job.id == UUID(str(job_id)), Job.tenant_id == tenant_id)
        )
        if job is None:
            return None
        return {
            "status": job.status,
            "priority": job.priority,
            "service_type": job.service_type,
            "customer_id": str(job.customer_id),
        }.get(path.split(".", 1)[1])

    if path.startswith("customer."):
        customer_id = payload.get("customer_id")
        if not customer_id:
            return None
        customer = session.scalar(
            select(Customer).where(
                Customer.id == UUID(str(customer_id)), Customer.tenant_id == tenant_id
            )
        )
        if customer is None:
            return None
        key = path.split(".", 1)[1]
        if key == "name":
            return customer.name
        if key == "status":
            return customer.status
        if key == "email":
            return customer.email
        if key == "phone":
            return payload.get("customer_phone")
        return None

    if path.startswith("invoice."):
        invoice_id = payload.get("invoice_id")
        if not invoice_id:
            return None
        inv = session.scalar(
            select(Invoice).where(
                Invoice.id == UUID(str(invoice_id)), Invoice.tenant_id == tenant_id
            )
        )
        if inv is None:
            return None
        key = path.split(".", 1)[1]
        if key == "total":
            return inv.total_amount
        if key == "balance_due":
            return inv.balance_due
        if key == "status":
            return inv.status
        return None

    if path.startswith("payment."):
        payment_id = payload.get("payment_id") or (
            event.entity_id if event.entity_type == "payment" else None
        )
        if not payment_id:
            return None
        pay = session.scalar(
            select(Payment).where(
                Payment.id == UUID(str(payment_id)), Payment.tenant_id == tenant_id
            )
        )
        if pay is None:
            return None
        key = path.split(".", 1)[1]
        if key == "amount":
            return pay.amount
        if key == "status":
            return pay.status
        return None

    if path.startswith("order."):
        order_id = payload.get("order_id") or (
            event.entity_id if event.entity_type == "order" else None
        )
        if not order_id:
            return None
        order = session.scalar(
            select(Order).where(
                Order.id == UUID(str(order_id)), Order.tenant_id == tenant_id
            )
        )
        return (
            None if order is None else order.status if path.endswith("status") else None
        )

    if path.startswith("estimate."):
        estimate_id = payload.get("estimate_id") or (
            event.entity_id if event.entity_type == "estimate" else None
        )
        if not estimate_id:
            return None
        est = session.scalar(
            select(Estimate).where(
                Estimate.id == UUID(str(estimate_id)), Estimate.tenant_id == tenant_id
            )
        )
        return None if est is None else est.status if path.endswith("status") else None

    if path.startswith("appointment."):
        appt_id = payload.get("appointment_id") or (
            event.entity_id if event.entity_type == "appointment" else None
        )
        if not appt_id:
            return None
        appt = session.scalar(
            select(Appointment).where(
                Appointment.id == UUID(str(appt_id)),
                Appointment.tenant_id == tenant_id,
            )
        )
        return (
            None if appt is None else appt.status if path.endswith("status") else None
        )

    return None


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == ConditionOperator.EXISTS.value:
        return left is not None and left != ""
    if op == ConditionOperator.NOT_EXISTS.value:
        return left is None or left == ""

    if op in {
        ConditionOperator.GREATER_THAN.value,
        ConditionOperator.GREATER_THAN_OR_EQUAL.value,
        ConditionOperator.LESS_THAN.value,
        ConditionOperator.LESS_THAN_OR_EQUAL.value,
    }:
        ld = _as_decimal(left)
        rd = _as_decimal(right)
        if ld is None or rd is None:
            return False
        if op == ConditionOperator.GREATER_THAN.value:
            return ld > rd
        if op == ConditionOperator.GREATER_THAN_OR_EQUAL.value:
            return ld >= rd
        if op == ConditionOperator.LESS_THAN.value:
            return ld < rd
        return ld <= rd

    ls = "" if left is None else str(left)
    if op == ConditionOperator.EQUALS.value:
        return ls == str(right)
    if op == ConditionOperator.NOT_EQUALS.value:
        return ls != str(right)
    if op == ConditionOperator.CONTAINS.value:
        return str(right) in ls
    if op == ConditionOperator.NOT_CONTAINS.value:
        return str(right) not in ls
    if op == ConditionOperator.STARTS_WITH.value:
        return ls.startswith(str(right))
    if op == ConditionOperator.ENDS_WITH.value:
        return ls.endswith(str(right))
    if op == ConditionOperator.IN.value:
        values = right if isinstance(right, list) else [right]
        return ls in {str(v) for v in values}
    if op == ConditionOperator.NOT_IN.value:
        values = right if isinstance(right, list) else [right]
        return ls not in {str(v) for v in values}
    raise ConditionError("invalid_operator", f"Unknown operator: {op}")


def evaluate_condition_node(
    session: Session,
    *,
    tenant_id: UUID,
    event: AutomationEvent,
    node: dict[str, Any] | None,
) -> bool:
    """Evaluate ALL/ANY/NOT trees or leaf predicates."""
    if not node:
        return True
    kind = str(node.get("op") or node.get("type") or "ALL").upper()
    if kind in {"ALL", "AND"}:
        children = node.get("conditions") or node.get("children") or []
        return all(
            evaluate_condition_node(session, tenant_id=tenant_id, event=event, node=c)
            for c in children
        )
    if kind in {"ANY", "OR"}:
        children = node.get("conditions") or node.get("children") or []
        if not children:
            return True
        return any(
            evaluate_condition_node(session, tenant_id=tenant_id, event=event, node=c)
            for c in children
        )
    if kind == "NOT":
        child = node.get("condition") or node.get("child")
        return not evaluate_condition_node(
            session, tenant_id=tenant_id, event=event, node=child
        )

    # Leaf: {field, operator, value}
    field = str(node.get("field") or "")
    operator = str(node.get("operator") or "")
    if operator not in {o.value for o in ConditionOperator}:
        raise ConditionError("invalid_operator", f"Unknown operator: {operator}")
    left = _resolve_field(session, tenant_id=tenant_id, event=event, path=field)
    return _compare(operator, left, node.get("value"))


def validate_condition_tree(node: dict[str, Any] | None) -> None:
    if not node:
        return
    kind = str(node.get("op") or node.get("type") or "").upper()
    if kind in {"ALL", "AND", "ANY", "OR"}:
        for child in node.get("conditions") or node.get("children") or []:
            validate_condition_tree(child)
        return
    if kind == "NOT":
        validate_condition_tree(node.get("condition") or node.get("child"))
        return
    field = str(node.get("field") or "")
    if field not in CONDITION_FIELDS:
        raise ConditionError("invalid_condition_field", f"Unknown field: {field}")
    operator = str(node.get("operator") or "")
    if operator not in {o.value for o in ConditionOperator}:
        raise ConditionError("invalid_operator", f"Unknown operator: {operator}")
