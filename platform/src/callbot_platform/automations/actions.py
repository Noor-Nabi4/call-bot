"""Execute automation actions through existing domain services."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.automation.webhooks import normalize_webhook_config
from callbot_platform.automations.constants import ActionType
from callbot_platform.automations.templates import render_template
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Customer, CustomerPhone, Tenant
from callbot_platform.db.models.automations import (
    AutomationActionExecution,
    AutomationEvent,
    AutomationTask,
)
from callbot_platform.db.models.invoices import Invoice
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class ActionError(CrmError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(code, message)
        self.retryable = retryable


def validate_action_config(
    action_type: str, config: dict[str, Any] | None
) -> dict[str, Any]:
    cfg = dict(config or {})
    if action_type not in {a.value for a in ActionType}:
        raise ActionError("invalid_action", f"Unknown action: {action_type}")
    if action_type == ActionType.WEBHOOK.value:
        return normalize_webhook_config(cfg)
    if action_type in {ActionType.SEND_SMS.value, ActionType.SEND_EMAIL.value}:
        body = str(cfg.get("body") or cfg.get("template") or "").strip()
        if not body:
            raise ActionError("invalid_action_config", "Message body/template required")
        return {"body": body[:2000], "subject": str(cfg.get("subject") or "")[:200]}
    if action_type == ActionType.CREATE_TASK.value:
        title = str(cfg.get("title") or "Follow up").strip()[:255]
        return {
            "title": title or "Follow up",
            "description": (str(cfg.get("description") or "").strip() or None),
            "due_hours": int(cfg.get("due_hours") or 24),
        }
    if action_type == ActionType.CREATE_JOB.value:
        return {
            "service_type": str(cfg.get("service_type") or "Follow-up").strip()[:128],
            "description": (str(cfg.get("description") or "").strip() or None),
            "priority": str(cfg.get("priority") or "NORMAL").strip().upper()[:32],
        }
    if action_type == ActionType.CREATE_APPOINTMENT.value:
        minutes = int(cfg.get("duration_minutes") or 60)
        if minutes < 15 or minutes > 480:
            raise ActionError("invalid_action_config", "duration_minutes out of range")
        return {"duration_minutes": minutes, "notes": str(cfg.get("notes") or "")[:500]}
    if action_type == ActionType.SEND_PAYMENT_LINK.value:
        return {}
    if action_type == ActionType.REQUEST_REVIEW.value:
        url = str(cfg.get("review_url") or "").strip()
        body = str(
            cfg.get("body")
            or "Thanks for choosing us! Please leave a review: {{review.url}}"
        ).strip()
        return {"review_url": url[:2048], "body": body[:2000], "channel": "sms"}
    return cfg


def _customer_context(
    session: Session, tenant_id: UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    customer_id = payload.get("customer_id")
    ctx: dict[str, Any] = {
        "business.name": "Your service provider",
        "review.url": "",
    }
    tenant = session.get(Tenant, tenant_id)
    if tenant is not None:
        ctx["business.name"] = tenant.name
    if not customer_id:
        return ctx
    customer = session.scalar(
        select(Customer).where(
            Customer.id == UUID(str(customer_id)), Customer.tenant_id == tenant_id
        )
    )
    if customer is None:
        return ctx
    phone = session.scalar(
        select(CustomerPhone).where(
            CustomerPhone.tenant_id == tenant_id,
            CustomerPhone.customer_id == customer.id,
        )
    )
    ctx.update(
        {
            "customer.first_name": customer.first_name or customer.name.split(" ")[0],
            "customer.name": customer.name,
            "customer.email": customer.email or "",
            "customer.phone": phone.e164 if phone else "",
            "job.number": payload.get("job_number") or "",
            "job.status": payload.get("job_status") or "",
            "invoice.number": payload.get("invoice_number") or "",
            "invoice.balance_due": str(payload.get("balance_due") or ""),
            "appointment.confirmation_code": payload.get("confirmation_code") or "",
        }
    )
    return ctx


class ActionExecutor:
    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(
        self,
        *,
        tenant_id: UUID,
        event: AutomationEvent,
        action_type: str,
        config: dict[str, Any],
        action_row: AutomationActionExecution,
        execution_id: UUID,
    ) -> dict[str, Any]:
        cfg = validate_action_config(action_type, config)
        if action_type == ActionType.SEND_SMS.value:
            return self._send_sms(tenant_id, event, cfg, action_row)
        if action_type == ActionType.SEND_EMAIL.value:
            return self._send_email(tenant_id, event, cfg, action_row)
        if action_type == ActionType.CREATE_TASK.value:
            return self._create_task(tenant_id, event, cfg, action_row, execution_id)
        if action_type == ActionType.CREATE_JOB.value:
            return self._create_job(tenant_id, event, cfg, action_row)
        if action_type == ActionType.CREATE_APPOINTMENT.value:
            return self._create_appointment(tenant_id, event, cfg, action_row)
        if action_type == ActionType.SEND_PAYMENT_LINK.value:
            return self._send_payment_link(tenant_id, event, action_row)
        if action_type == ActionType.REQUEST_REVIEW.value:
            return self._request_review(tenant_id, event, cfg, action_row)
        if action_type == ActionType.WEBHOOK.value:
            return self._webhook(tenant_id, event, cfg, action_row)
        raise ActionError("invalid_action", f"Unsupported action: {action_type}")

    def _send_sms(
        self,
        tenant_id: UUID,
        event: AutomationEvent,
        cfg: dict[str, Any],
        action_row: AutomationActionExecution,
    ) -> dict[str, Any]:
        ctx = _customer_context(self._session, tenant_id, event.payload or {})
        to = ctx.get("customer.phone") or ""
        if not to:
            raise ActionError("missing_recipient", "Customer phone not found")
        body = render_template(cfg["body"], ctx)
        row = NotificationService(self._session).enqueue_sms(
            tenant_id=tenant_id,
            to_address=str(to),
            body=body,
            idempotency_key=action_row.idempotency_key,
        )
        return {"notification_id": row.get("id"), "channel": "sms"}

    def _send_email(
        self,
        tenant_id: UUID,
        event: AutomationEvent,
        cfg: dict[str, Any],
        action_row: AutomationActionExecution,
    ) -> dict[str, Any]:
        ctx = _customer_context(self._session, tenant_id, event.payload or {})
        to = ctx.get("customer.email") or ""
        if not to:
            raise ActionError("missing_recipient", "Customer email not found")
        body = render_template(cfg["body"], ctx)
        row = NotificationService(self._session).enqueue_email(
            tenant_id=tenant_id,
            to_address=str(to),
            body=body,
            idempotency_key=action_row.idempotency_key,
        )
        return {"notification_id": row.get("id"), "channel": "email"}

    def _create_task(
        self,
        tenant_id: UUID,
        event: AutomationEvent,
        cfg: dict[str, Any],
        action_row: AutomationActionExecution,
        execution_id: UUID,
    ) -> dict[str, Any]:
        existing = self._session.scalar(
            select(AutomationTask).where(
                AutomationTask.tenant_id == tenant_id,
                AutomationTask.idempotency_key == action_row.idempotency_key,
            )
        )
        if existing is not None:
            return {"task_id": str(existing.id), "idempotent": True}
        customer_id = (event.payload or {}).get("customer_id")
        task = AutomationTask(
            tenant_id=tenant_id,
            title=cfg["title"],
            description=cfg.get("description"),
            due_at=datetime.now(UTC) + timedelta(hours=int(cfg.get("due_hours") or 24)),
            source="automation",
            source_event_id=event.id,
            source_execution_id=execution_id,
            customer_id=UUID(str(customer_id)) if customer_id else None,
            idempotency_key=action_row.idempotency_key,
            created_by="automation",
        )
        try:
            with self._session.begin_nested():
                self._session.add(task)
                self._session.flush()
        except IntegrityError:
            existing = self._session.scalar(
                select(AutomationTask).where(
                    AutomationTask.tenant_id == tenant_id,
                    AutomationTask.idempotency_key == action_row.idempotency_key,
                )
            )
            if existing is None:
                raise
            return {"task_id": str(existing.id), "idempotent": True}
        return {"task_id": str(task.id)}

    def _create_job(
        self,
        tenant_id: UUID,
        event: AutomationEvent,
        cfg: dict[str, Any],
        action_row: AutomationActionExecution,
    ) -> dict[str, Any]:
        from callbot_platform.crm.jobs import JobService

        payload = event.payload or {}
        customer_id = payload.get("customer_id")
        if not customer_id:
            raise ActionError("missing_customer", "customer_id required to create job")
        # Self-trigger protection: never CREATE_JOB from JOB_CREATED chains.
        if event.event_type == "JOB_CREATED":
            raise ActionError(
                "loop_blocked",
                "CREATE_JOB is not allowed on JOB_CREATED to prevent recursion",
            )
        job = JobService(self._session).create(
            tenant_id,
            customer_id=UUID(str(customer_id)),
            actor="automation",
            service_type=cfg["service_type"],
            description=cfg.get("description"),
            priority=cfg.get("priority"),
            location_id=(
                UUID(str(payload["location_id"]))
                if payload.get("location_id")
                else None
            ),
            idempotency_key=action_row.idempotency_key,
        )
        return {"job_id": job["id"], "job_number": job.get("job_number")}

    def _create_appointment(
        self,
        tenant_id: UUID,
        event: AutomationEvent,
        cfg: dict[str, Any],
        action_row: AutomationActionExecution,
    ) -> dict[str, Any]:
        from callbot_platform.crm.appointments.service import AppointmentService

        payload = event.payload or {}
        customer_id = payload.get("customer_id")
        if not customer_id:
            raise ActionError(
                "missing_customer", "customer_id required to create appointment"
            )
        starts = datetime.now(UTC) + timedelta(days=1)
        ends = starts + timedelta(minutes=int(cfg["duration_minutes"]))
        if event.event_type == "APPOINTMENT_CREATED":
            raise ActionError(
                "loop_blocked",
                "CREATE_APPOINTMENT is not allowed on APPOINTMENT_CREATED",
            )
        appt = AppointmentService(self._session).create(
            tenant_id,
            customer_id=UUID(str(customer_id)),
            starts_at=starts,
            ends_at=ends,
            actor="automation",
            notes=cfg.get("notes") or None,
            idempotency_key=action_row.idempotency_key,
        )
        return {"appointment_id": appt["id"]}

    def _send_payment_link(
        self,
        tenant_id: UUID,
        event: AutomationEvent,
        action_row: AutomationActionExecution,
    ) -> dict[str, Any]:
        from callbot_platform.crm.payments.service import PaymentService

        payload = event.payload or {}
        invoice_id = payload.get("invoice_id")
        if not invoice_id:
            raise ActionError("missing_invoice", "invoice_id required for payment link")
        inv = self._session.scalar(
            select(Invoice).where(
                Invoice.id == UUID(str(invoice_id)), Invoice.tenant_id == tenant_id
            )
        )
        if inv is None:
            raise ActionError("invoice_not_found", "Invoice not found")
        if inv.balance_due <= 0:
            raise ActionError("invoice_paid", "Invoice has no balance due")
        result = PaymentService(self._session).create_payment_link(
            tenant_id,
            inv.id,
            actor="automation",
            idempotency_key=action_row.idempotency_key,
        )
        return {
            "payment_id": result.get("id") or result.get("payment_id"),
            "checkout_url": result.get("checkout_url") or result.get("url"),
        }

    def _request_review(
        self,
        tenant_id: UUID,
        event: AutomationEvent,
        cfg: dict[str, Any],
        action_row: AutomationActionExecution,
    ) -> dict[str, Any]:
        ctx = _customer_context(self._session, tenant_id, event.payload or {})
        ctx["review.url"] = cfg.get("review_url") or ""
        to = ctx.get("customer.phone") or ""
        if not to:
            raise ActionError("missing_recipient", "Customer phone not found")
        body = render_template(cfg["body"], ctx)
        row = NotificationService(self._session).enqueue_sms(
            tenant_id=tenant_id,
            to_address=str(to),
            body=body,
            idempotency_key=action_row.idempotency_key,
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor="automation",
            action="automation.review_requested",
            resource_ids={"event_id": str(event.id)},
            payload_summary={"notification_id": row.get("id")},
        )
        return {"notification_id": row.get("id"), "channel": "sms"}

    def _webhook(
        self,
        tenant_id: UUID,
        event: AutomationEvent,
        cfg: dict[str, Any],
        action_row: AutomationActionExecution,
    ) -> dict[str, Any]:
        row = NotificationService(self._session).enqueue_webhook(
            tenant_id=tenant_id,
            url=cfg["url"],
            event=event.event_type,
            event_payload={
                "event_id": str(event.id),
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": str(event.entity_id),
                "payload": event.payload or {},
                "occurred_at": event.occurred_at.isoformat(),
            },
            secret=cfg.get("secret"),
            timeout_sec=float(cfg.get("timeout_sec") or 5),
            rule_id=str(action_row.execution_id),
            idempotency_key=action_row.idempotency_key,
        )
        return {"notification_id": row.get("id"), "channel": "webhook"}
