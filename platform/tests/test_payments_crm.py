"""Phase 19 Payments: checkout link flow, apply, refund, isolation (Stripe mocked)."""

from __future__ import annotations

import types
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices import InvoiceService
from callbot_platform.crm.payments import PaymentService
from callbot_platform.crm.payments.webhooks import InvoicePaymentWebhookService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Tenant


def _setup(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Payer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        email=f"payer-{uuid.uuid4().hex[:6]}@example.test",
        actor="t",
    )
    prod = ProductCatalogService(session).create(
        tenant_id,
        name="Widget",
        sku=f"P-{uuid.uuid4().hex[:6]}",
        price="100.00",
        tax_rate="0",
        actor="t",
    )
    inv = InvoiceService(session).create(
        tenant_id,
        customer_id=uuid.UUID(customer["id"]),
        actor="t",
        items=[
            {
                "item_type": "PRODUCT",
                "product_id": uuid.UUID(prod["id"]),
                "quantity": 1,
            }
        ],
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    sent = InvoiceService(session).send(tenant_id, uuid.UUID(inv["id"]), actor="t")
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "invoice_id": uuid.UUID(sent["id"]),
        "total": Decimal(sent["total_amount"]),
    }


def _fake_checkout(
    monkeypatch: pytest.MonkeyPatch,
    *,
    session_id: str = "cs_test_1",
    payment_intent: str | None = None,
):
    pi = payment_intent or f"pi_{session_id}"
    session_obj = types.SimpleNamespace(
        id=session_id,
        url=f"https://checkout.stripe.test/{session_id}",
        payment_intent=pi,
    )

    class _Checkout:
        class Session:
            @staticmethod
            def create(**kwargs):
                return session_obj

    monkeypatch.setattr(
        "callbot_platform.crm.payments.service.stripe",
        types.SimpleNamespace(
            checkout=_Checkout(),
            api_key=None,
            error=types.SimpleNamespace(StripeError=Exception),
            Refund=types.SimpleNamespace(
                create=lambda **kw: types.SimpleNamespace(
                    id="re_test_1", status="succeeded", amount=kw.get("amount")
                )
            ),
        ),
    )
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    from callbot_platform.config import get_settings

    get_settings.cache_clear()


def test_payment_link_apply_partial_and_refund(
    session: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_checkout(monkeypatch)
    setup = _setup(session, tenant.id)
    payments = PaymentService(session)

    link = payments.create_payment_link(
        tenant.id,
        setup["invoice_id"],
        actor="t",
        amount="40.00",
        idempotency_key="pl-1",
    )
    assert link["status"] == "PROCESSING"
    assert link["checkout_url"]
    assert Decimal(link["amount"]) == Decimal("40.0000")

    again = payments.create_payment_link(
        tenant.id,
        setup["invoice_id"],
        actor="t",
        amount="40.00",
        idempotency_key="pl-1",
    )
    assert again["id"] == link["id"]

    applied = payments.mark_succeeded_and_apply(
        tenant.id,
        uuid.UUID(link["id"]),
        provider_payment_intent_id="pi_cs_test_1",
        actor="stripe_webhook",
    )
    assert applied["status"] == "SUCCEEDED"
    assert applied["applied_to_invoice"] is True

    inv = InvoiceService(session).get(tenant.id, setup["invoice_id"])
    assert inv["status"] == "PARTIALLY_PAID"
    assert Decimal(inv["amount_paid"]) == Decimal("40.0000")

    # Second payment for remainder
    _fake_checkout(monkeypatch, session_id="cs_test_2")
    link2 = payments.create_payment_link(
        tenant.id,
        setup["invoice_id"],
        actor="t",
        amount="60.00",
        idempotency_key="pl-2",
    )
    payments.mark_succeeded_and_apply(
        tenant.id,
        uuid.UUID(link2["id"]),
        provider_payment_intent_id="pi_cs_test_2",
    )
    inv = InvoiceService(session).get(tenant.id, setup["invoice_id"])
    assert inv["status"] == "PAID"
    assert Decimal(inv["balance_due"]) == Decimal("0.0000")

    # Idempotent re-apply
    payments.mark_succeeded_and_apply(tenant.id, uuid.UUID(link2["id"]))
    inv2 = InvoiceService(session).get(tenant.id, setup["invoice_id"])
    assert Decimal(inv2["amount_paid"]) == Decimal("100.0000")

    refunded = payments.request_refund(
        tenant.id,
        uuid.UUID(link2["id"]),
        actor="t",
        amount="30.00",
        idempotency_key="rf-1",
    )
    assert refunded["payment"]["status"] == "PARTIALLY_REFUNDED"
    inv = InvoiceService(session).get(tenant.id, setup["invoice_id"])
    assert Decimal(inv["amount_paid"]) == Decimal("70.0000")
    assert inv["status"] == "PARTIALLY_PAID"


def test_payment_tenant_isolation(
    session: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_checkout(monkeypatch)
    setup = _setup(session, tenant.id)
    other = Tenant(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    payments = PaymentService(session)
    link = payments.create_payment_link(
        tenant.id, setup["invoice_id"], actor="t", idempotency_key="iso-1"
    )
    with pytest.raises(CrmError, match="not found"):
        payments.get(other.id, uuid.UUID(link["id"]))


def test_webhook_rejects_bad_signature(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    import stripe as real_stripe

    from callbot_platform.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "callbot_platform.crm.payments.webhooks.stripe.Webhook.construct_event",
        MagicMock(
            side_effect=real_stripe.error.SignatureVerificationError("bad", "sig")
        ),
    )
    svc = InvoicePaymentWebhookService(session)
    with pytest.raises(CrmError) as exc:
        svc.construct_event(b"{}", "t=1,v1=x")
    assert exc.value.code == "webhook_invalid"
