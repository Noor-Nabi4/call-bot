"""Invoice payment application (Phase 19 links external payment_id)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices.calculation import InvoiceCalculationService
from callbot_platform.crm.invoices.constants import (
    PAYMENT_ELIGIBLE_STATUSES,
    InvoiceStatus,
)
from callbot_platform.crm.invoices.money import (
    require_money,
    serialize_money,
)
from callbot_platform.crm.invoices.serialize import serialize_invoice
from callbot_platform.crm.invoices.transitions import InvoiceTransitionService
from callbot_platform.db.models.invoices import Invoice, InvoicePaymentApplication
from callbot_platform.telephony.audit import write_audit

_MONEY_ZERO = Decimal("0.0000")


class InvoicePaymentService:
    """Authoritative path to update amount_paid and payment status."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._transitions = InvoiceTransitionService(session)

    def record_payment(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        *,
        amount: object,
        actor: str,
        payment_id: UUID | None = None,
        idempotency_key: str | None = None,
        reference_note: str | None = None,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None
        if key:
            existing = self._session.scalar(
                select(InvoicePaymentApplication).where(
                    InvoicePaymentApplication.tenant_id == tenant_id,
                    InvoicePaymentApplication.idempotency_key == key,
                )
            )
            if existing is not None:
                inv = self._load(tenant_id, existing.invoice_id)
                return serialize_invoice(inv, include_history=True, include_payments=True)

        pay_amount = require_money(amount, field="amount")
        if pay_amount <= 0:
            raise CrmError("invalid_amount", "Payment amount must be positive")

        invoice = self._load(tenant_id, invoice_id, for_update=True)
        if invoice.status == InvoiceStatus.VOID.value:
            raise CrmError("invoice_void", "Cannot apply payment to void invoice")
        if invoice.status == InvoiceStatus.DRAFT.value:
            raise CrmError("invoice_not_sent", "Invoice must be sent before payment")
        if invoice.status not in PAYMENT_ELIGIBLE_STATUSES | {InvoiceStatus.PAID.value}:
            raise CrmError(
                "invalid_status",
                f"Cannot apply payment in status {invoice.status}",
            )
        if invoice.status == InvoiceStatus.PAID.value:
            raise CrmError("invoice_paid", "Invoice is already fully paid")

        remaining = invoice.balance_due or _MONEY_ZERO
        if pay_amount > remaining:
            raise CrmError(
                "payment_exceeds_balance",
                "Payment amount exceeds balance_due",
            )

        app = InvoicePaymentApplication(
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            payment_id=payment_id,
            amount=pay_amount,
            idempotency_key=key,
            reference_note=reference_note,
            created_by=actor,
        )
        try:
            with self._session.begin_nested():
                self._session.add(app)
                self._session.flush()
        except IntegrityError as exc:
            if key:
                raced = self._session.scalar(
                    select(InvoicePaymentApplication).where(
                        InvoicePaymentApplication.tenant_id == tenant_id,
                        InvoicePaymentApplication.idempotency_key == key,
                    )
                )
                if raced is not None:
                    inv = self._load(tenant_id, raced.invoice_id)
                    return serialize_invoice(
                        inv, include_history=True, include_payments=True
                    )
            raise CrmError("payment_conflict", "Could not record payment") from exc

        invoice.amount_paid = (invoice.amount_paid or _MONEY_ZERO) + pay_amount
        InvoiceCalculationService.sync_balance(invoice)

        if invoice.balance_due == _MONEY_ZERO:
            target = InvoiceStatus.PAID.value
        else:
            target = InvoiceStatus.PARTIALLY_PAID.value

        if invoice.status != target:
            self._transitions.transition(
                tenant_id,
                invoice.id,
                to_status=target,
                actor=actor,
                reason="payment_applied",
                metadata={"amount": serialize_money(pay_amount)},
                skip_overdue_check=True,
            )
        else:
            invoice.updated_by = actor
            invoice.updated_at = datetime.now(UTC)
            self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="invoice.payment_applied",
            resource_ids={
                "invoice_id": str(invoice.id),
                "application_id": str(app.id),
                "payment_id": str(payment_id) if payment_id else None,
            },
            idempotency_key=key,
            payload_summary={"amount": serialize_money(pay_amount)},
        )
        inv = self._load(tenant_id, invoice.id)
        return serialize_invoice(inv, include_history=True, include_payments=True)

    def _load(
        self, tenant_id: UUID, invoice_id: UUID, *, for_update: bool = False
    ) -> Invoice:
        q = (
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
            .options(
                selectinload(Invoice.items),
                selectinload(Invoice.status_history),
                selectinload(Invoice.customer),
                selectinload(Invoice.payment_applications),
            )
        )
        if for_update:
            q = q.with_for_update()
        row = self._session.scalar(q)
        if row is None:
            raise CrmError("not_found", "Invoice not found for tenant")
        return row
