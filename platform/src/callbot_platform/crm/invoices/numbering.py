"""Concurrency-safe tenant-scoped invoice number allocation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.db.models.invoices import InvoiceNumberCounter


def allocate_invoice_number(session: Session, tenant_id: UUID) -> str:
    """Return next INV-###### for the tenant. Safe under concurrent writers."""
    row = session.scalar(
        select(InvoiceNumberCounter)
        .where(InvoiceNumberCounter.tenant_id == tenant_id)
        .with_for_update()
    )
    if row is None:
        row = InvoiceNumberCounter(tenant_id=tenant_id, last_value=0)
        try:
            with session.begin_nested():
                session.add(row)
                session.flush()
        except IntegrityError:
            row = session.scalar(
                select(InvoiceNumberCounter)
                .where(InvoiceNumberCounter.tenant_id == tenant_id)
                .with_for_update()
            )
            if row is None:
                raise RuntimeError("invoice number counter unavailable") from None
        else:
            row = session.scalar(
                select(InvoiceNumberCounter)
                .where(InvoiceNumberCounter.tenant_id == tenant_id)
                .with_for_update()
            )
            if row is None:
                raise RuntimeError("invoice number counter missing after insert")

    row.last_value += 1
    row.updated_at = datetime.now(UTC)
    session.flush()
    return f"INV-{row.last_value:06d}"
