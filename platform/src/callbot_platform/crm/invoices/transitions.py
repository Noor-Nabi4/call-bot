"""Invoice status transition policy."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices.constants import (
    INVOICE_STATUSES,
    PAYMENT_ELIGIBLE_STATUSES,
    VALID_TRANSITIONS,
    InvoiceStatus,
)
from callbot_platform.crm.invoices.serialize import (
    serialize_invoice,
    serialize_status_history,
)
from callbot_platform.db.models.invoices import Invoice, InvoiceStatusHistory
from callbot_platform.telephony.audit import write_audit


def normalize_status(value: str) -> str:
    raw = (value or "").strip().upper()
    if raw not in INVOICE_STATUSES:
        raise CrmError("invalid_status", f"Unknown invoice status: {value}")
    return raw


def is_overdue(invoice: Invoice, *, now: datetime | None = None) -> bool:
    if invoice.status not in PAYMENT_ELIGIBLE_STATUSES:
        return False
    if (invoice.balance_due or 0) <= 0:
        return False
    at = now or datetime.now(UTC)
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    due = invoice.due_date
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return due < at


class InvoiceTransitionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def history(self, tenant_id: UUID, invoice_id: UUID) -> list[dict[str, Any]]:
        invoice = self._session.scalar(
            select(Invoice).where(
                Invoice.id == invoice_id, Invoice.tenant_id == tenant_id
            )
        )
        if invoice is None:
            raise CrmError("not_found", "Invoice not found for tenant")
        rows = list(
            self._session.scalars(
                select(InvoiceStatusHistory)
                .where(
                    InvoiceStatusHistory.tenant_id == tenant_id,
                    InvoiceStatusHistory.invoice_id == invoice_id,
                )
                .order_by(
                    InvoiceStatusHistory.created_at.asc(),
                    InvoiceStatusHistory.id.asc(),
                )
            ).all()
        )
        return [serialize_status_history(r) for r in rows]

    def transition(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        *,
        to_status: str,
        actor: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        skip_overdue_check: bool = False,
    ) -> dict[str, Any]:
        invoice = self._session.scalar(
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
            .options(
                selectinload(Invoice.items),
                selectinload(Invoice.status_history),
                selectinload(Invoice.customer),
                selectinload(Invoice.payment_applications),
            )
            .with_for_update()
        )
        if invoice is None:
            raise CrmError("not_found", "Invoice not found for tenant")

        target = normalize_status(to_status)
        current = invoice.status
        if current == target:
            return serialize_invoice(
                invoice, include_history=True, include_payments=True
            )
        if (current, target) not in VALID_TRANSITIONS:
            raise CrmError(
                "invalid_transition",
                f"Cannot transition invoice from {current} to {target}",
            )
        if (
            target == InvoiceStatus.OVERDUE.value
            and not skip_overdue_check
            and not is_overdue(invoice)
        ):
            raise CrmError("invoice_not_overdue", "Invoice is not past due_date")

        now = datetime.now(UTC)
        prev = invoice.status
        invoice.status = target
        invoice.updated_by = actor
        invoice.updated_at = now
        if target == InvoiceStatus.SENT.value:
            invoice.sent_at = now
        if target == InvoiceStatus.VOID.value:
            invoice.voided_at = now

        self._session.add(
            InvoiceStatusHistory(
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                from_status=prev,
                to_status=target,
                reason=(reason.strip()[:500] if reason and reason.strip() else None),
                actor_type="user",
                actor_id=actor,
                metadata_json=metadata or {},
            )
        )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="invoice.status_changed",
            resource_ids={
                "invoice_id": str(invoice.id),
                "from_status": prev,
                "to_status": target,
            },
            payload_summary={"reason": reason} if reason else None,
        )
        return serialize_invoice(
            invoice, include_history=True, include_payments=True
        )

    def maybe_mark_overdue(
        self, invoice: Invoice, *, actor: str = "system"
    ) -> bool:
        if invoice.status not in PAYMENT_ELIGIBLE_STATUSES:
            return False
        if not is_overdue(invoice):
            return False
        if invoice.status == InvoiceStatus.OVERDUE.value:
            return False
        self.transition(
            invoice.tenant_id,
            invoice.id,
            to_status=InvoiceStatus.OVERDUE.value,
            actor=actor,
            reason="past_due_date",
            skip_overdue_check=True,
        )
        return True
