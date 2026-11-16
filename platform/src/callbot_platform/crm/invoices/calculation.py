"""Authoritative invoice total and balance calculations."""

from __future__ import annotations

from decimal import Decimal

from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.invoices import Invoice

_MONEY_ZERO = Decimal("0.0000")


class InvoiceCalculationService:
    """Single calculation path for API, admin UI, payments, and tests."""

    @staticmethod
    def apply_invoice_totals(
        invoice: Invoice,
        *,
        line_payloads: list[dict],
        invoice_discount: Decimal,
    ) -> None:
        subtotal = sum((p["line_subtotal"] for p in line_payloads), _MONEY_ZERO)
        line_discount = sum((p["discount_amount"] for p in line_payloads), _MONEY_ZERO)
        tax_amount = sum((p["tax_amount"] for p in line_payloads), _MONEY_ZERO)
        discount_amount = line_discount + invoice_discount
        if discount_amount > subtotal:
            raise CrmError(
                "invalid_discount_amount",
                "Total discount cannot exceed invoice subtotal",
            )
        total_amount = subtotal - discount_amount + tax_amount
        if total_amount < 0:
            raise CrmError("invalid_total", "Invoice total cannot be negative")
        invoice.subtotal = subtotal
        invoice.discount_amount = discount_amount
        invoice.invoice_discount = invoice_discount
        invoice.tax_amount = tax_amount
        invoice.total_amount = total_amount
        InvoiceCalculationService.sync_balance(invoice)

    @staticmethod
    def sync_balance(invoice: Invoice) -> None:
        paid = invoice.amount_paid or _MONEY_ZERO
        if paid < 0:
            raise CrmError("invalid_amount_paid", "amount_paid cannot be negative")
        total = invoice.total_amount or _MONEY_ZERO
        if paid > total:
            raise CrmError(
                "overpayment",
                "amount_paid cannot exceed total_amount",
            )
        invoice.balance_due = total - paid
