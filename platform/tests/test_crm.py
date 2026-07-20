"""CRM repository isolation and idempotency tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.repos import (
    CallRepository,
    CrmError,
    CustomerRepository,
    LeadRepository,
)
from callbot_platform.db.models import Tenant


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Beta Plumbing", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def test_customer_upsert_and_lookup(session: Session, tenant: Tenant) -> None:
    repo = CustomerRepository(session)
    created = repo.upsert(
        tenant.id, name="Noor Nabi", phone="+15551112222", address="123 Main"
    )
    assert created["name"] == "Noor Nabi"
    found = repo.lookup_by_phone(tenant.id, "+1 555 111 2222")
    assert found is not None
    assert found["id"] == created["id"]
    assert "+15551112222" in found["phones"]


def test_same_phone_allowed_across_tenants(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    a = CustomerRepository(session).upsert(
        tenant.id, name="A", phone="+15553334444"
    )
    b = CustomerRepository(session).upsert(
        tenant_b.id, name="B", phone="+15553334444"
    )
    assert a["id"] != b["id"]
    assert CustomerRepository(session).lookup_by_phone(tenant.id, "+15553334444")[
        "name"
    ] == "A"
    assert CustomerRepository(session).lookup_by_phone(tenant_b.id, "+15553334444")[
        "name"
    ] == "B"


def test_tenant_isolation_lookup(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    CustomerRepository(session).upsert(
        tenant.id, name="Secret", phone="+15555556666"
    )
    assert (
        CustomerRepository(session).lookup_by_phone(tenant_b.id, "+15555556666")
        is None
    )


def test_tenant_isolation_get_lead(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Cust", phone="+15557778888"
    )
    lead = LeadRepository(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="AC repair",
        urgency="high",
    )
    assert LeadRepository(session).get(tenant.id, uuid.UUID(lead["id"])) is not None
    assert LeadRepository(session).get(tenant_b.id, uuid.UUID(lead["id"])) is None


def test_lead_idempotency(session: Session, tenant: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Cust", phone="+15559990000"
    )
    first = LeadRepository(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="Heating",
        idempotency_key="idem-1",
    )
    second = LeadRepository(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="Heating DUPLICATE",
        idempotency_key="idem-1",
    )
    assert first["id"] == second["id"]
    assert first["reference_code"] == second["reference_code"]
    assert second["service_type"] == "Heating"


def test_lead_rejects_foreign_customer(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Cust", phone="+15551231212"
    )
    with pytest.raises(CrmError) as exc:
        LeadRepository(session).create(
            tenant_b.id,
            customer_id=uuid.UUID(customer["id"]),
            service_type="Leak",
        )
    assert exc.value.code == "customer_not_found"


def test_call_lifecycle(session: Session, tenant: Tenant) -> None:
    started = CallRepository(session).start(
        tenant.id,
        room_name="call-test",
        job_id="AJ_test",
        caller_number="+15550001111",
    )
    ended = CallRepository(session).end(
        tenant.id,
        call_id=uuid.UUID(started["id"]),
        status="closed",
        disconnect_reason="participant_disconnected",
        metrics={"duration_sec": 12},
    )
    assert ended["status"] == "closed"
    assert ended["metrics"]["duration_sec"] == 12
    assert ended["billable_seconds"] is not None
    assert ended["billable_seconds"] >= 0
