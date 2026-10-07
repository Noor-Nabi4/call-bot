"""Phase 18 Invoices: lifecycle, money, payments, isolation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices import InvoiceService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Tenant


def _setup(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        email=f"buyer-{uuid.uuid4().hex[:6]}@example.test",
        actor="t",
    )
    prod = ProductCatalogService(session).create(
        tenant_id,
        name="Widget",
        sku=f"W-{uuid.uuid4().hex[:6]}",
        price="25.00",
        tax_rate="10",
        actor="t",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "product_id": uuid.UUID(prod["id"]),
    }


def test_invoice_create_send_pay_void(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = InvoiceService(session)
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "PRODUCT",
                "product_id": setup["product_id"],
                "quantity": 2,
            }
        ],
        invoice_discount="2.00",
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    assert created["invoice_number"] == "INV-000001"
    assert created["status"] == "DRAFT"
    assert Decimal(created["total_amount"]) == Decimal("53.0000")
    assert Decimal(created["balance_due"]) == Decimal("53.0000")

    iid = uuid.UUID(created["id"])
    sent = api.send(tenant.id, iid, actor="t")
    assert sent["status"] == "SENT"

    partial = api.payments.record_payment(
        tenant.id, iid, amount="20.00", actor="t", idempotency_key="pay-1"
    )
    assert partial["status"] == "PARTIALLY_PAID"
    assert Decimal(partial["amount_paid"]) == Decimal("20.0000")

    paid = api.payments.record_payment(
        tenant.id, iid, amount="33.00", actor="t", idempotency_key="pay-2"
    )
    assert paid["status"] == "PAID"
    assert Decimal(paid["balance_due"]) == Decimal("0.0000")

    with pytest.raises(CrmError, match="already fully paid"):
        api.payments.record_payment(
            tenant.id, iid, amount="1.00", actor="t", idempotency_key="pay-3"
        )


def test_invoice_void_and_tenant_isolation(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    other = Tenant(name="Other", slug=f"oth-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()

    api = InvoiceService(session)
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "CUSTOM",
                "name": "Fee",
                "unit_price": "10.00",
                "quantity": 1,
            }
        ],
    )
    iid = uuid.UUID(created["id"])
    api.send(tenant.id, iid, actor="t")
    voided = api.void(tenant.id, iid, actor="t", reason="mistake")
    assert voided["status"] == "VOID"

    with pytest.raises(CrmError, match="not found"):
        api.get(other.id, iid)


def test_invoice_rejects_client_totals_via_immutable_fields(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = InvoiceService(session)
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "CUSTOM",
                "name": "Line",
                "unit_price": "100.00",
                "quantity": 1,
            }
        ],
    )
    iid = uuid.UUID(created["id"])
    api.send(tenant.id, iid, actor="t")
    with pytest.raises(CrmError):
        api.update(
            tenant.id,
            iid,
            actor="t",
            items=[
                {
                    "item_type": "CUSTOM",
                    "name": "Line",
                    "unit_price": "100.00",
                    "quantity": 1,
                }
            ],
        )
