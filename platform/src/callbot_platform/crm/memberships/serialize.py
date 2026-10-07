"""Serialize membership domain rows for API / AI tools."""

from __future__ import annotations

from typing import Any

from callbot_platform.crm.memberships.money import serialize_money
from callbot_platform.db.models.memberships import (
    CustomerMembership,
    MembershipBillingPeriod,
    MembershipHistory,
    MembershipPlan,
    MembershipPlanService,
)


def serialize_plan_service(row: MembershipPlanService) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "plan_id": str(row.plan_id),
        "service_id": str(row.service_id),
        "included_quantity": int(row.included_quantity),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_plan(
    plan: MembershipPlan, *, include_services: bool = True
) -> dict[str, Any]:
    services = []
    if include_services and plan.included_services is not None:
        services = [serialize_plan_service(s) for s in plan.included_services]
    return {
        "id": str(plan.id),
        "tenant_id": str(plan.tenant_id),
        "name": plan.name,
        "description": plan.description,
        "status": plan.status,
        "monthly_price": serialize_money(plan.monthly_price),
        "annual_price": serialize_money(plan.annual_price),
        "currency": plan.currency,
        "priority_scheduling": bool(plan.priority_scheduling),
        "discount_type": plan.discount_type,
        "discount_value": (
            serialize_money(plan.discount_value)
            if plan.discount_value is not None
            else None
        ),
        "included_services": services,
        "archived_at": plan.archived_at.isoformat() if plan.archived_at else None,
        "created_by": plan.created_by,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


def serialize_membership(
    row: CustomerMembership,
    *,
    plan: MembershipPlan | None = None,
    include_history: bool = False,
    history: list[MembershipHistory] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "customer_id": str(row.customer_id),
        "plan_id": str(row.plan_id),
        "billing_interval": row.billing_interval,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "current_period_start": row.current_period_start.isoformat(),
        "current_period_end": row.current_period_end.isoformat(),
        "cancel_at_period_end": bool(row.cancel_at_period_end),
        "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        "renewed_at": row.renewed_at.isoformat() if row.renewed_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "pending_plan_id": str(row.pending_plan_id) if row.pending_plan_id else None,
        "pending_billing_interval": row.pending_billing_interval,
        "last_invoice_id": str(row.last_invoice_id) if row.last_invoice_id else None,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if plan is not None:
        payload["plan"] = serialize_plan(plan)
    if include_history and history is not None:
        payload["history"] = [serialize_history(h) for h in history]
    return payload


def serialize_history(row: MembershipHistory) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "membership_id": str(row.membership_id),
        "customer_id": str(row.customer_id),
        "event_type": row.event_type,
        "from_plan_id": str(row.from_plan_id) if row.from_plan_id else None,
        "to_plan_id": str(row.to_plan_id) if row.to_plan_id else None,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "effective_at": row.effective_at.isoformat(),
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "metadata": row.metadata_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_billing_period(row: MembershipBillingPeriod) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "membership_id": str(row.membership_id),
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "invoice_id": str(row.invoice_id) if row.invoice_id else None,
        "amount": serialize_money(row.amount),
        "currency": row.currency,
        "status": row.status,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
