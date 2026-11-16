"""Invoice CRM facade (Phase 18)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates import EstimateService
from callbot_platform.crm.invoices.calculation import InvoiceCalculationService
from callbot_platform.crm.invoices.constants import (
    DEFAULT_INVOICE_STATUS,
    EDITABLE_STATUSES,
    VOIDABLE_STATUSES,
    InvoiceStatus,
)
from callbot_platform.crm.invoices.fingerprint import invoice_create_fingerprint
from callbot_platform.crm.invoices.money import (
    money_or_zero,
    normalize_currency,
    serialize_money,
)
from callbot_platform.crm.invoices.numbering import allocate_invoice_number
from callbot_platform.crm.invoices.payments import InvoicePaymentService
from callbot_platform.crm.invoices.search import InvoiceSearchService
from callbot_platform.crm.invoices.serialize import serialize_invoice
from callbot_platform.crm.invoices.transitions import (
    InvoiceTransitionService,
    is_overdue,
)
from callbot_platform.db.models import Customer
from callbot_platform.db.models.estimates import Estimate
from callbot_platform.db.models.invoices import (
    Invoice,
    InvoiceItem,
    InvoiceStatusHistory,
)
from callbot_platform.db.models.jobs import Job
from callbot_platform.db.models.orders import Order
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.telephony.audit import write_audit


class InvoiceService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self.search = InvoiceSearchService(session)
        self.transitions = InvoiceTransitionService(session)
        self.payments = InvoicePaymentService(session)
        self._estimates = EstimateService(session)

    def _load(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        *,
        for_update: bool = False,
        include_history: bool = False,
        include_payments: bool = False,
    ) -> Invoice:
        q = select(Invoice).where(
            Invoice.id == invoice_id, Invoice.tenant_id == tenant_id
        )
        if for_update:
            q = q.with_for_update()
        opts = [selectinload(Invoice.customer), selectinload(Invoice.items)]
        if include_history:
            opts.append(selectinload(Invoice.status_history))
        if include_payments:
            opts.append(selectinload(Invoice.payment_applications))
        q = q.options(*opts)
        row = self._session.scalar(q)
        if row is None:
            raise CrmError("not_found", "Invoice not found for tenant")
        return row

    def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        row = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")
        return row

    def _validate_optional_refs(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        job_id: UUID | None,
        order_id: UUID | None,
        estimate_id: UUID | None,
    ) -> None:
        if job_id is not None:
            job = self._session.scalar(
                select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
            )
            if job is None:
                raise CrmError("job_not_found", "Job not found for tenant")
            if job.customer_id != customer_id:
                raise CrmError(
                    "job_customer_mismatch",
                    "Job customer does not match invoice customer",
                )
        if order_id is not None:
            order = self._session.scalar(
                select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
            )
            if order is None:
                raise CrmError("order_not_found", "Order not found for tenant")
            if order.customer_id != customer_id:
                raise CrmError(
                    "order_customer_mismatch",
                    "Order customer does not match invoice customer",
                )
        if estimate_id is not None:
            est = self._session.scalar(
                select(Estimate).where(
                    Estimate.id == estimate_id, Estimate.tenant_id == tenant_id
                )
            )
            if est is None:
                raise CrmError("estimate_not_found", "Estimate not found for tenant")
            if est.customer_id != customer_id:
                raise CrmError(
                    "estimate_customer_mismatch",
                    "Estimate customer does not match invoice customer",
                )

    def _parse_dates(
        self, issue_date: datetime | None, due_date: datetime | None
    ) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)
        issue = issue_date or now
        if issue.tzinfo is None:
            issue = issue.replace(tzinfo=UTC)
        due = due_date or (issue + timedelta(days=30))
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        if due < issue:
            raise CrmError("invalid_due_date", "due_date must be on or after issue_date")
        return issue, due

    def _resolve_line(
        self,
        tenant_id: UUID,
        raw: dict[str, Any],
        *,
        sort_order: int,
    ) -> dict[str, Any]:
        mapped = dict(raw)
        if mapped.get("discount_amount") is not None and mapped.get("discount_total") is None:
            mapped["discount_total"] = mapped["discount_amount"]
        if mapped.get("tax_amount") is not None and mapped.get("tax_total") is None:
            mapped["tax_total"] = mapped["tax_amount"]
        payload = self._estimates._resolve_line(
            tenant_id,
            mapped,
            sort_order=sort_order,
            default_pricebook_id=None,
        )
        return {
            "item_type": payload["item_type"],
            "service_id": payload["service_id"],
            "product_id": payload["product_id"],
            "variant_id": payload["variant_id"],
            "description": payload["name_snapshot"],
            "quantity": payload["quantity"],
            "unit_price": payload["unit_price"],
            "discount_amount": payload["discount_total"],
            "tax_amount": payload["tax_total"],
            "line_subtotal": payload["line_subtotal"],
            "line_total": payload["line_total"],
            "pricing_source_snapshot": payload.get("pricing_source_snapshot"),
            "sort_order": sort_order,
        }

    def _replace_items(
        self, invoice: Invoice, line_payloads: list[dict[str, Any]]
    ) -> None:
        for existing in list(invoice.items or []):
            self._session.delete(existing)
        self._session.flush()
        for payload in line_payloads:
            self._session.add(
                InvoiceItem(
                    tenant_id=invoice.tenant_id,
                    invoice_id=invoice.id,
                    **payload,
                )
            )
        self._session.flush()

    def get(self, tenant_id: UUID, invoice_id: UUID) -> dict[str, Any]:
        invoice = self._load(
            tenant_id,
            invoice_id,
            include_history=True,
            include_payments=True,
        )
        if is_overdue(invoice):
            try:
                self.transitions.transition(
                    tenant_id,
                    invoice_id,
                    to_status=InvoiceStatus.OVERDUE.value,
                    actor="system",
                    reason="past_due_date",
                    skip_overdue_check=True,
                )
                invoice = self._load(
                    tenant_id,
                    invoice_id,
                    include_history=True,
                    include_payments=True,
                )
            except CrmError:
                pass
        return serialize_invoice(
            invoice, include_history=True, include_payments=True
        )

    def list(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.search(tenant_id, **kwargs)

    def create(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        actor: str,
        items: list[dict[str, Any]],
        job_id: UUID | None = None,
        order_id: UUID | None = None,
        estimate_id: UUID | None = None,
        currency: str | None = None,
        invoice_discount: object | None = None,
        issue_date: datetime | None = None,
        due_date: datetime | None = None,
        notes: str | None = None,
        terms: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None
        if not items:
            raise CrmError("items_required", "Invoice requires at least one line item")

        customer = self._require_customer(tenant_id, customer_id)
        self._validate_optional_refs(
            tenant_id,
            customer_id=customer.id,
            job_id=job_id,
            order_id=order_id,
            estimate_id=estimate_id,
        )
        cur = normalize_currency(currency)
        idisc = money_or_zero(invoice_discount, field="invoice_discount")
        issue, due = self._parse_dates(issue_date, due_date)
        notes_clean = notes.strip() if notes and notes.strip() else None
        terms_clean = terms.strip() if terms and terms.strip() else None

        line_payloads = [
            self._resolve_line(
                tenant_id,
                raw,
                sort_order=int(raw.get("sort_order") or idx),
            )
            for idx, raw in enumerate(items)
        ]

        req_hash = invoice_create_fingerprint(
            customer_id=customer.id,
            job_id=job_id,
            order_id=order_id,
            estimate_id=estimate_id,
            currency=cur,
            invoice_discount=serialize_money(idisc),
            issue_date=issue.isoformat(),
            due_date=due.isoformat(),
            items=items,
            notes=notes_clean,
            terms=terms_clean,
        )

        if key:
            existing = self._session.scalar(
                select(Invoice).where(
                    Invoice.tenant_id == tenant_id, Invoice.idempotency_key == key
                )
            )
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    and existing.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different invoice payload",
                    )
                return self.get(tenant_id, existing.id)

        number = allocate_invoice_number(self._session, tenant_id)
        invoice = Invoice(
            tenant_id=tenant_id,
            invoice_number=number,
            customer_id=customer.id,
            job_id=job_id,
            order_id=order_id,
            estimate_id=estimate_id,
            status=DEFAULT_INVOICE_STATUS,
            currency=cur,
            issue_date=issue,
            due_date=due,
            amount_paid=Decimal("0"),
            notes=notes_clean,
            terms=terms_clean,
            idempotency_key=key,
            idempotency_request_hash=req_hash if key else None,
            created_by=actor,
            updated_by=actor,
        )
        InvoiceCalculationService.apply_invoice_totals(
            invoice, line_payloads=line_payloads, invoice_discount=idisc
        )
        try:
            with self._session.begin_nested():
                self._session.add(invoice)
                self._session.flush()
        except IntegrityError as exc:
            if key:
                raced = self._session.scalar(
                    select(Invoice).where(
                        Invoice.tenant_id == tenant_id,
                        Invoice.idempotency_key == key,
                    )
                )
                if raced is not None:
                    if (
                        raced.idempotency_request_hash
                        and raced.idempotency_request_hash != req_hash
                    ):
                        raise CrmError(
                            "idempotency_conflict",
                            "Idempotency-Key reused with a different invoice payload",
                        ) from exc
                    return self.get(tenant_id, raced.id)
            raise CrmError("invoice_conflict", "Could not create invoice") from exc

        for payload in line_payloads:
            self._session.add(
                InvoiceItem(tenant_id=tenant_id, invoice_id=invoice.id, **payload)
            )
        self._session.add(
            InvoiceStatusHistory(
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                from_status=None,
                to_status=InvoiceStatus.DRAFT.value,
                reason="created",
                actor_type="user",
                actor_id=actor,
                metadata_json={"event": "INVOICE_CREATED"},
            )
        )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="invoice.created",
            resource_ids={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "customer_id": str(customer.id),
            },
            idempotency_key=key,
            payload_summary={
                "total_amount": str(invoice.total_amount),
                "currency": invoice.currency,
            },
        )
        from callbot_platform.automations.publishers import publish_invoice_created

        publish_invoice_created(
            self._session,
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            customer_id=customer.id,
            total=invoice.total_amount,
            balance_due=invoice.balance_due,
            invoice_number=invoice.invoice_number,
        )
        return self.get(tenant_id, invoice.id)

    def update(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        *,
        actor: str,
        customer_id: UUID | None = None,
        job_id: UUID | None = None,
        order_id: UUID | None = None,
        estimate_id: UUID | None = None,
        clear_job: bool = False,
        clear_order: bool = False,
        clear_estimate: bool = False,
        invoice_discount: object | None = None,
        issue_date: datetime | None = None,
        due_date: datetime | None = None,
        notes: str | None = None,
        clear_notes: bool = False,
        terms: str | None = None,
        clear_terms: bool = False,
        items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        invoice = self._load(tenant_id, invoice_id, for_update=True)
        if invoice.status not in EDITABLE_STATUSES:
            raise CrmError(
                "invoice_immutable",
                f"Cannot update invoice in status {invoice.status}",
            )
        cid = customer_id or invoice.customer_id
        if customer_id is not None:
            self._require_customer(tenant_id, customer_id)
            invoice.customer_id = cid
        jid = None if clear_job else (job_id if job_id is not None else invoice.job_id)
        oid = None if clear_order else (order_id if order_id is not None else invoice.order_id)
        eid = (
            None
            if clear_estimate
            else (estimate_id if estimate_id is not None else invoice.estimate_id)
        )
        invoice.job_id = jid
        invoice.order_id = oid
        invoice.estimate_id = eid
        self._validate_optional_refs(
            tenant_id,
            customer_id=cid,
            job_id=jid,
            order_id=oid,
            estimate_id=eid,
        )

        if issue_date is not None or due_date is not None:
            issue, due = self._parse_dates(
                issue_date or invoice.issue_date,
                due_date or invoice.due_date,
            )
            invoice.issue_date = issue
            invoice.due_date = due
        if clear_notes:
            invoice.notes = None
        elif notes is not None:
            invoice.notes = notes.strip() or None
        if clear_terms:
            invoice.terms = None
        elif terms is not None:
            invoice.terms = terms.strip() or None

        idisc = (
            money_or_zero(invoice_discount, field="invoice_discount")
            if invoice_discount is not None
            else invoice.invoice_discount
        )
        if items is not None:
            if not items:
                raise CrmError("items_required", "Invoice requires at least one line")
            payloads = [
                self._resolve_line(
                    tenant_id,
                    raw,
                    sort_order=int(raw.get("sort_order") or idx),
                )
                for idx, raw in enumerate(items)
            ]
            self._replace_items(invoice, payloads)
            InvoiceCalculationService.apply_invoice_totals(
                invoice, line_payloads=payloads, invoice_discount=idisc
            )
        else:
            current = [
                {
                    "line_subtotal": i.line_subtotal,
                    "discount_amount": i.discount_amount,
                    "tax_amount": i.tax_amount,
                }
                for i in (invoice.items or [])
            ]
            InvoiceCalculationService.apply_invoice_totals(
                invoice, line_payloads=current, invoice_discount=idisc
            )

        invoice.updated_by = actor
        invoice.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="invoice.updated",
            resource_ids={"invoice_id": str(invoice.id)},
        )
        return self.get(tenant_id, invoice.id)

    def send(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        *,
        actor: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None
        invoice = self._load(
            tenant_id, invoice_id, for_update=True, include_history=True
        )
        if invoice.status == InvoiceStatus.SENT.value and key:
            for row in invoice.status_history or []:
                meta = row.metadata_json or {}
                if meta.get("send_idempotency_key") == key:
                    return self.get(tenant_id, invoice_id)
        if invoice.status != InvoiceStatus.DRAFT.value:
            raise CrmError(
                "invalid_transition",
                f"Cannot send invoice in status {invoice.status}",
            )
        if not invoice.items:
            raise CrmError("items_required", "Cannot send an empty invoice")

        current = [
            {
                "line_subtotal": i.line_subtotal,
                "discount_amount": i.discount_amount,
                "tax_amount": i.tax_amount,
            }
            for i in invoice.items
        ]
        InvoiceCalculationService.apply_invoice_totals(
            invoice,
            line_payloads=current,
            invoice_discount=invoice.invoice_discount,
        )

        result = self.transitions.transition(
            tenant_id,
            invoice_id,
            to_status=InvoiceStatus.SENT.value,
            actor=actor,
            reason="sent",
            metadata={
                "event": "INVOICE_SENT",
                "send_idempotency_key": key,
            },
        )

        customer = invoice.customer
        if customer and customer.email:
            body = (
                f"Invoice {invoice.invoice_number} for "
                f"{serialize_money(invoice.total_amount)} {invoice.currency} "
                f"is due {invoice.due_date.date().isoformat()}."
            )
            NotificationService(self._session).enqueue_email(
                tenant_id=tenant_id,
                to_address=customer.email,
                body=body,
                idempotency_key=key or f"invoice_sent:{invoice.id}",
            )

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="invoice.sent",
            resource_ids={"invoice_id": str(invoice.id)},
            idempotency_key=key,
        )
        return result

    def void(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        *,
        actor: str,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None
        invoice = self._load(
            tenant_id, invoice_id, for_update=True, include_history=True
        )
        if invoice.status == InvoiceStatus.VOID.value:
            return self.get(tenant_id, invoice_id)
        if invoice.status not in VOIDABLE_STATUSES:
            raise CrmError(
                "invalid_transition",
                f"Cannot void invoice in status {invoice.status}",
            )
        result = self.transitions.transition(
            tenant_id,
            invoice_id,
            to_status=InvoiceStatus.VOID.value,
            actor=actor,
            reason=reason or "voided",
            metadata={"void_idempotency_key": key},
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="invoice.voided",
            resource_ids={"invoice_id": str(invoice.id)},
            idempotency_key=key,
        )
        return result

    def history(self, tenant_id: UUID, invoice_id: UUID) -> list[dict[str, Any]]:
        return self.transitions.history(tenant_id, invoice_id)
