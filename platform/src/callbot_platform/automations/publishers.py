"""Thin helpers for domain services to emit Phase 22 events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.automations.constants import AutomationEventType
from callbot_platform.automations.events import (
    emit_automation_event,
    schedule_appointment_reminder,
)


def publish_job_created(
    session: Session,
    *,
    tenant_id: UUID,
    job_id: UUID,
    customer_id: UUID,
    job_number: str,
    location_id: UUID | None = None,
    status: str | None = None,
) -> None:
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=AutomationEventType.JOB_CREATED.value,
        source="jobs",
        entity_type="job",
        entity_id=job_id,
        payload={
            "job_id": str(job_id),
            "customer_id": str(customer_id),
            "job_number": job_number,
            "location_id": str(location_id) if location_id else None,
            "job_status": status,
        },
        idempotency_key=f"job-created:{job_id}",
    )


def publish_job_completed(
    session: Session,
    *,
    tenant_id: UUID,
    job_id: UUID,
    customer_id: UUID,
    job_number: str,
    invoice_id: UUID | None = None,
) -> None:
    payload: dict[str, Any] = {
        "job_id": str(job_id),
        "customer_id": str(customer_id),
        "job_number": job_number,
        "job_status": "COMPLETED",
    }
    if invoice_id:
        payload["invoice_id"] = str(invoice_id)
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=AutomationEventType.JOB_COMPLETED.value,
        source="jobs",
        entity_type="job",
        entity_id=job_id,
        payload=payload,
        idempotency_key=f"job-completed:{job_id}",
    )


def publish_lead_created(
    session: Session, *, tenant_id: UUID, lead_id: UUID, customer_id: UUID | None = None
) -> None:
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=AutomationEventType.LEAD_CREATED.value,
        source="leads",
        entity_type="lead",
        entity_id=lead_id,
        payload={
            "lead_id": str(lead_id),
            "customer_id": str(customer_id) if customer_id else None,
        },
        idempotency_key=f"lead-created:{lead_id}",
    )


def publish_appointment_created(
    session: Session,
    *,
    tenant_id: UUID,
    appointment_id: UUID,
    customer_id: UUID,
    starts_at: Any,
    confirmation_code: str | None = None,
) -> None:
    payload = {
        "appointment_id": str(appointment_id),
        "customer_id": str(customer_id),
        "confirmation_code": confirmation_code,
    }
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=AutomationEventType.APPOINTMENT_CREATED.value,
        source="appointments",
        entity_type="appointment",
        entity_id=appointment_id,
        payload=payload,
        idempotency_key=f"appointment-created:{appointment_id}",
    )
    if starts_at is not None:
        schedule_appointment_reminder(
            session,
            tenant_id=tenant_id,
            appointment_id=appointment_id,
            starts_at=starts_at,
            payload=payload,
        )


def publish_technician_dispatched(
    session: Session,
    *,
    tenant_id: UUID,
    job_id: UUID,
    technician_id: UUID,
    customer_id: UUID | None = None,
) -> None:
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=AutomationEventType.TECHNICIAN_DISPATCHED.value,
        source="dispatch",
        entity_type="job",
        entity_id=job_id,
        payload={
            "job_id": str(job_id),
            "technician_id": str(technician_id),
            "customer_id": str(customer_id) if customer_id else None,
        },
        idempotency_key=f"tech-dispatched:{job_id}:{technician_id}",
    )


def publish_estimate_event(
    session: Session,
    *,
    tenant_id: UUID,
    estimate_id: UUID,
    event_type: str,
    customer_id: UUID | None = None,
) -> None:
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=event_type,
        source="estimates",
        entity_type="estimate",
        entity_id=estimate_id,
        payload={
            "estimate_id": str(estimate_id),
            "customer_id": str(customer_id) if customer_id else None,
        },
        idempotency_key=f"estimate:{event_type}:{estimate_id}",
    )


def publish_invoice_created(
    session: Session,
    *,
    tenant_id: UUID,
    invoice_id: UUID,
    customer_id: UUID,
    total: Any = None,
    balance_due: Any = None,
    invoice_number: str | None = None,
) -> None:
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=AutomationEventType.INVOICE_CREATED.value,
        source="invoices",
        entity_type="invoice",
        entity_id=invoice_id,
        payload={
            "invoice_id": str(invoice_id),
            "customer_id": str(customer_id),
            "invoice_number": invoice_number,
            "balance_due": str(balance_due) if balance_due is not None else None,
        },
        idempotency_key=f"invoice-created:{invoice_id}",
    )


def publish_payment_completed(
    session: Session,
    *,
    tenant_id: UUID,
    payment_id: UUID,
    invoice_id: UUID,
    customer_id: UUID,
    amount: Any,
) -> None:
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=AutomationEventType.PAYMENT_COMPLETED.value,
        source="payments",
        entity_type="payment",
        entity_id=payment_id,
        payload={
            "payment_id": str(payment_id),
            "invoice_id": str(invoice_id),
            "customer_id": str(customer_id),
            "amount": str(amount),
        },
        idempotency_key=f"payment-completed:{payment_id}",
    )


def publish_order_event(
    session: Session,
    *,
    tenant_id: UUID,
    order_id: UUID,
    event_type: str,
    customer_id: UUID | None = None,
    status: str | None = None,
) -> None:
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=event_type,
        source="orders",
        entity_type="order",
        entity_id=order_id,
        payload={
            "order_id": str(order_id),
            "customer_id": str(customer_id) if customer_id else None,
            "order_status": status,
        },
        idempotency_key=f"order:{event_type}:{order_id}",
    )


def publish_call_completed(
    session: Session,
    *,
    tenant_id: UUID,
    call_id: UUID,
    customer_id: UUID | None = None,
) -> None:
    emit_automation_event(
        session,
        tenant_id=tenant_id,
        event_type=AutomationEventType.CALL_COMPLETED.value,
        source="calls",
        entity_type="call",
        entity_id=call_id,
        payload={
            "call_id": str(call_id),
            "customer_id": str(customer_id) if customer_id else None,
        },
        idempotency_key=f"call-completed:{call_id}",
    )
