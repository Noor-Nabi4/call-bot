"""Invoice serialization."""

from __future__ import annotations

from typing import Any

from callbot_platform.crm.invoices.money import serialize_money
from callbot_platform.db.models.invoices import (
    Invoice,
    InvoiceItem,
    InvoicePaymentApplication,
    InvoiceStatusHistory,
)


def serialize_item(item: InvoiceItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "item_type": item.item_type,
        "service_id": str(item.service_id) if item.service_id else None,
        "product_id": str(item.product_id) if item.product_id else None,
        "variant_id": str(item.variant_id) if item.variant_id else None,
        "description": item.description,
        "quantity": serialize_money(item.quantity),
        "unit_price": serialize_money(item.unit_price),
        "discount_amount": serialize_money(item.discount_amount),
        "tax_amount": serialize_money(item.tax_amount),
        "line_subtotal": serialize_money(item.line_subtotal),
        "line_total": serialize_money(item.line_total),
        "pricing_source_snapshot": item.pricing_source_snapshot,
        "sort_order": item.sort_order,
        "metadata": item.metadata_json or {},
    }


def serialize_status_history(row: InvoiceStatusHistory) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "from_status": row.from_status,
        "to_status": row.to_status,
        "reason": row.reason,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "metadata": row.metadata_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_payment_application(row: InvoicePaymentApplication) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "invoice_id": str(row.invoice_id),
        "payment_id": str(row.payment_id) if row.payment_id else None,
        "amount": serialize_money(row.amount),
        "reference_note": row.reference_note,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_invoice(
    invoice: Invoice,
    *,
    include_history: bool = False,
    include_payments: bool = False,
) -> dict[str, Any]:
    customer = None
    if invoice.customer is not None:
        customer = {
            "id": str(invoice.customer.id),
            "name": invoice.customer.name,
            "display_name": invoice.customer.name,
            "email": invoice.customer.email,
        }
    items = sorted(invoice.items or [], key=lambda i: (i.sort_order, str(i.id)))
    payload: dict[str, Any] = {
        "id": str(invoice.id),
        "tenant_id": str(invoice.tenant_id),
        "invoice_number": invoice.invoice_number,
        "customer_id": str(invoice.customer_id),
        "customer": customer,
        "job_id": str(invoice.job_id) if invoice.job_id else None,
        "order_id": str(invoice.order_id) if invoice.order_id else None,
        "estimate_id": str(invoice.estimate_id) if invoice.estimate_id else None,
        "status": invoice.status,
        "currency": invoice.currency,
        "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "subtotal": serialize_money(invoice.subtotal),
        "discount_amount": serialize_money(invoice.discount_amount),
        "invoice_discount": serialize_money(invoice.invoice_discount),
        "tax_amount": serialize_money(invoice.tax_amount),
        "total_amount": serialize_money(invoice.total_amount),
        "amount_paid": serialize_money(invoice.amount_paid),
        "balance_due": serialize_money(invoice.balance_due),
        "notes": invoice.notes,
        "terms": invoice.terms,
        "sent_at": invoice.sent_at.isoformat() if invoice.sent_at else None,
        "voided_at": invoice.voided_at.isoformat() if invoice.voided_at else None,
        "items": [serialize_item(i) for i in items],
        "created_by": invoice.created_by,
        "updated_by": invoice.updated_by,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
    }
    if include_history:
        history = sorted(
            invoice.status_history or [],
            key=lambda h: (h.created_at, str(h.id)),
        )
        payload["status_history"] = [serialize_status_history(h) for h in history]
    if include_payments:
        apps = sorted(
            invoice.payment_applications or [],
            key=lambda p: (p.created_at, str(p.id)),
        )
        payload["payments"] = [serialize_payment_application(p) for p in apps]
    return payload
