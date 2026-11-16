"""Phase 20 Memberships: plans, subscribe/pay, cancel, renew, entitlements, isolation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.appointments.service import AppointmentService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices.payments import InvoicePaymentService
from callbot_platform.crm.memberships import (
    MembershipEntitlementService,
    MembershipService,
)
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.memberships import MembershipEntitlementUsage


def _customer(session: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    row = CustomerService(session).create(
        tenant_id,
        name="Member",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        email=f"member-{uuid.uuid4().hex[:6]}@example.test",
        actor="t",
    )
    return uuid.UUID(row["id"])


def _service(session: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    svc = ServicesPricebookService(session).create_service(
        tenant_id,
        name=f"Inspection-{uuid.uuid4().hex[:6]}",
        base_price="100.00",
        duration_minutes=60,
        actor="t",
    )
    return uuid.UUID(svc["id"])


def _active_plan(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    name: str | None = None,
    service_id: uuid.UUID | None = None,
    monthly: str = "49.00",
    annual: str = "490.00",
    discount_type: str | None = "PERCENTAGE",
    discount_value: str | None = "10",
    priority: bool = True,
) -> dict:
    ms = MembershipService(session)
    plan = ms.create_plan(
        tenant_id,
        actor="t",
        name=name or f"Gold-{uuid.uuid4().hex[:6]}",
        monthly_price=monthly,
        annual_price=annual,
        priority_scheduling=priority,
        discount_type=discount_type,
        discount_value=discount_value,
        included_services=(
            [{"service_id": service_id, "included_quantity": 1}] if service_id else []
        ),
        status="DRAFT",
    )
    return ms.activate_plan(tenant_id, uuid.UUID(plan["id"]), actor="t")


def _pay_invoice(session: Session, tenant_id: uuid.UUID, invoice_id: uuid.UUID) -> None:
    from callbot_platform.crm.invoices import InvoiceService

    inv = InvoiceService(session).get(tenant_id, invoice_id)
    InvoicePaymentService(session).record_payment(
        tenant_id,
        invoice_id,
        amount=inv["balance_due"],
        actor="t",
        idempotency_key=f"pay-{invoice_id}",
    )


def test_plan_subscribe_activate_cancel_and_discount(
    session: Session, tenant: Tenant
) -> None:
    service_id = _service(session, tenant.id)
    customer_id = _customer(session, tenant.id)
    plan = _active_plan(session, tenant.id, service_id=service_id)
    ms = MembershipService(session)

    sub = ms.subscribe(
        tenant.id,
        customer_id=customer_id,
        plan_id=uuid.UUID(plan["id"]),
        billing_interval="MONTHLY",
        actor="t",
        idempotency_key="sub-1",
        create_payment_link=False,
    )
    assert sub["status"] == "PENDING"
    assert sub["last_invoice_id"]
    again = ms.subscribe(
        tenant.id,
        customer_id=customer_id,
        plan_id=uuid.UUID(plan["id"]),
        billing_interval="MONTHLY",
        actor="t",
        idempotency_key="sub-1",
        create_payment_link=False,
    )
    assert again["id"] == sub["id"]

    _pay_invoice(session, tenant.id, uuid.UUID(sub["last_invoice_id"]))
    active = ms.get_membership(tenant.id, uuid.UUID(sub["id"]))
    assert active["status"] == "ACTIVE"

    priced = MembershipEntitlementService(session).apply_service_discount(
        tenant.id, customer_id, unit_price="100.00"
    )
    assert Decimal(priced["final_unit_price"]) == Decimal("90.0000")

    cancelled = ms.cancel(tenant.id, uuid.UUID(sub["id"]), actor="t", immediate=False)
    assert cancelled["cancel_at_period_end"] is True
    assert cancelled["status"] == "ACTIVE"


def test_one_open_membership_and_tenant_isolation(
    session: Session, tenant: Tenant
) -> None:
    customer_id = _customer(session, tenant.id)
    plan = _active_plan(session, tenant.id)
    ms = MembershipService(session)
    sub = ms.subscribe(
        tenant.id,
        customer_id=customer_id,
        plan_id=uuid.UUID(plan["id"]),
        billing_interval="MONTHLY",
        actor="t",
        create_payment_link=False,
    )
    with pytest.raises(CrmError) as exc:
        ms.subscribe(
            tenant.id,
            customer_id=customer_id,
            plan_id=uuid.UUID(plan["id"]),
            billing_interval="ANNUAL",
            actor="t",
            create_payment_link=False,
        )
    assert exc.value.code == "membership_already_active"

    other = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    with pytest.raises(CrmError) as exc2:
        ms.get_membership(other.id, uuid.UUID(sub["id"]))
    assert exc2.value.code == "not_found"


def test_renew_idempotent_and_upgrade_next_period(
    session: Session, tenant: Tenant
) -> None:
    customer_id = _customer(session, tenant.id)
    gold = _active_plan(session, tenant.id, name=f"Gold-{uuid.uuid4().hex[:4]}")
    plat = _active_plan(
        session,
        tenant.id,
        name=f"Plat-{uuid.uuid4().hex[:4]}",
        monthly="99.00",
        annual="990.00",
    )
    ms = MembershipService(session)
    sub = ms.subscribe(
        tenant.id,
        customer_id=customer_id,
        plan_id=uuid.UUID(gold["id"]),
        billing_interval="MONTHLY",
        actor="t",
        create_payment_link=False,
    )
    _pay_invoice(session, tenant.id, uuid.UUID(sub["last_invoice_id"]))

    changed = ms.upgrade(
        tenant.id,
        uuid.UUID(sub["id"]),
        target_plan_id=uuid.UUID(plat["id"]),
        actor="t",
        idempotency_key="up-1",
    )
    assert changed["pending_plan_id"] == plat["id"]
    assert changed["plan_id"] == gold["id"]

    r1 = ms.renew(tenant.id, uuid.UUID(sub["id"]), actor="t", create_payment_link=False)
    r2 = ms.renew(tenant.id, uuid.UUID(sub["id"]), actor="t", create_payment_link=False)
    assert r1["billing_period"]["id"] == r2["billing_period"]["id"]
    assert r1["plan_id"] == plat["id"]

    _pay_invoice(session, tenant.id, uuid.UUID(r1["billing_period"]["invoice_id"]))
    after = ms.get_membership(tenant.id, uuid.UUID(sub["id"]))
    assert after["status"] == "ACTIVE"
    assert after["plan_id"] == plat["id"]


def test_entitlement_single_use_per_period(session: Session, tenant: Tenant) -> None:
    service_id = _service(session, tenant.id)
    customer_id = _customer(session, tenant.id)
    plan = _active_plan(session, tenant.id, service_id=service_id)
    ms = MembershipService(session)
    sub = ms.subscribe(
        tenant.id,
        customer_id=customer_id,
        plan_id=uuid.UUID(plan["id"]),
        billing_interval="MONTHLY",
        actor="t",
        create_payment_link=False,
    )
    _pay_invoice(session, tenant.id, uuid.UUID(sub["last_invoice_id"]))

    # Clear any usage created by unrelated hooks.
    session.query(MembershipEntitlementUsage).filter_by(
        tenant_id=tenant.id, membership_id=uuid.UUID(sub["id"])
    ).delete()
    session.flush()

    a1 = AppointmentService(session).create(
        tenant.id,
        customer_id=customer_id,
        starts_at=datetime.now(UTC) + timedelta(days=3, hours=10),
        actor="t",
        service_id=service_id,
        duration_minutes=60,
        idempotency_key=f"a1-{uuid.uuid4().hex[:6]}",
    )
    # First booking consumes included entitlement via appointment hook.
    remaining = MembershipEntitlementService(session).remaining_for_service(
        tenant.id, customer_id, service_id
    )
    assert remaining == 0

    a2 = AppointmentService(session).create(
        tenant.id,
        customer_id=customer_id,
        starts_at=datetime.now(UTC) + timedelta(days=4, hours=10),
        actor="t",
        service_id=service_id,
        duration_minutes=60,
        idempotency_key=f"a2-{uuid.uuid4().hex[:6]}",
    )
    assert a2["id"] != a1["id"]
    with pytest.raises(CrmError) as exc:
        MembershipEntitlementService(session).consume_entitlement(
            tenant.id,
            customer_id=customer_id,
            service_id=service_id,
            appointment_id=uuid.UUID(a2["id"]),
            actor="t",
        )
    assert exc.value.code == "entitlement_exhausted"


def test_cross_tenant_plan_service_rejected(session: Session, tenant: Tenant) -> None:
    other = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    foreign_service = _service(session, other.id)
    ms = MembershipService(session)
    with pytest.raises(CrmError) as exc:
        ms.create_plan(
            tenant.id,
            actor="t",
            name=f"Bad-{uuid.uuid4().hex[:4]}",
            monthly_price="10",
            included_services=[{"service_id": foreign_service, "included_quantity": 1}],
        )
    assert exc.value.code == "service_not_found"
