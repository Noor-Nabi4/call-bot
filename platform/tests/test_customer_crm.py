"""Phase 4 Customer CRM: CRUD, locations, search, timeline, isolation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.repos.customer_repo import CustomerRepository
from callbot_platform.db.models import (
    Appointment,
    Call,
    Customer,
    Job,
    Lead,
    Tenant,
)
from callbot_platform.domain.phone import normalize_e164


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def test_voice_upsert_compat_and_email_normalization(
    session: Session, tenant: Tenant
) -> None:
    repo = CustomerRepository(session)
    created = repo.upsert(
        tenant.id,
        name="Ada Lovelace",
        phone="+1 (555) 123-4567",
        email="Ada@Example.COM",
        address="1 Analytical Engine Rd",
    )
    assert created["name"] == "Ada Lovelace"
    assert created["display_name"] == "Ada Lovelace"
    assert created["email"] == "ada@example.com"
    assert created["email_normalized"] == "ada@example.com"
    assert created["status"] == "ACTIVE"
    assert created["phones"] == [normalize_e164("+1 (555) 123-4567")]

    again = repo.upsert(
        tenant.id,
        name="Ada L.",
        phone="+15551234567",
        email="ada@example.com",
    )
    assert again["id"] == created["id"]
    assert again["name"] == "Ada L."
    looked = repo.lookup_by_phone(tenant.id, "+15551234567")
    assert looked is not None
    assert looked["id"] == created["id"]
    # Formatted input with country code still resolves via normalize_e164
    looked2 = repo.lookup_by_phone(tenant.id, "+1 (555) 123-4567")
    assert looked2 is not None
    assert looked2["id"] == created["id"]


def test_customer_crud_archive_restore(session: Session, tenant: Tenant) -> None:
    svc = CustomerService(session)
    created = svc.create(
        tenant.id,
        first_name="Grace",
        last_name="Hopper",
        phone="+15551110001",
        email="grace@navy.mil",
        notes="COBOL pioneer",
        tags=["vip", "VIP"],
        actor="tester",
    )
    assert created["display_name"] == "Grace Hopper"
    assert created["first_name"] == "Grace"
    assert len(created["tags"]) == 1
    assert created["tags"][0]["name"].lower() == "vip"

    cid = uuid.UUID(created["id"])
    updated = svc.update(
        tenant.id, cid, actor="tester", status="INACTIVE", notes="Updated"
    )
    assert updated["status"] == "INACTIVE"
    assert updated["notes"] == "Updated"

    archived = svc.archive(tenant.id, cid, actor="tester")
    assert archived["archived_at"] is not None
    listed = svc.list(tenant.id)
    assert all(c["id"] != created["id"] for c in listed["customers"])

    with pytest.raises(CrmError) as exc:
        svc.update(tenant.id, cid, actor="tester", notes="nope")
    assert exc.value.code == "customer_archived"

    restored = svc.restore(tenant.id, cid, actor="tester")
    assert restored["archived_at"] is None
    listed2 = svc.list(tenant.id)
    assert any(c["id"] == created["id"] for c in listed2["customers"])


def test_locations_primary_and_validation(session: Session, tenant: Tenant) -> None:
    svc = CustomerService(session)
    cust = svc.create(tenant.id, name="Loc Cust", phone="+15551110002")
    cid = uuid.UUID(cust["id"])

    first = svc.locations.create_location(
        tenant.id,
        cid,
        address_line_1="100 First St",
        city="Austin",
        state="TX",
        postal_code="78701",
        country="us",
        access_instructions="Gate code 1234",
        actor="tester",
    )
    assert first["is_primary"] is True
    assert first["country"] == "US"

    second = svc.locations.create_location(
        tenant.id,
        cid,
        address_line_1="200 Second Ave",
        city="Dallas",
        is_primary=True,
        actor="tester",
    )
    assert second["is_primary"] is True
    locs = svc.locations.list_locations(tenant.id, cid)
    primaries = [loc for loc in locs if loc["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["id"] == second["id"]

    with pytest.raises(CrmError) as exc:
        svc.locations.create_location(
            tenant.id, cid, address_line_1="Bad", latitude=100.0
        )
    assert exc.value.code == "invalid_latitude"

    archived = svc.locations.archive_location(
        tenant.id, cid, uuid.UUID(second["id"]), actor="tester"
    )
    assert archived["archived_at"] is not None
    assert archived["is_primary"] is False
    remaining = svc.locations.list_locations(tenant.id, cid)
    assert len(remaining) == 1
    assert remaining[0]["is_primary"] is True
    assert remaining[0]["id"] == first["id"]


def test_search_phone_email_name_address_pagination(
    session: Session, tenant: Tenant
) -> None:
    svc = CustomerService(session)
    a = svc.create(
        tenant.id,
        name="Jonathan Smith",
        phone="+15551110003",
        email="jon.smith@example.com",
    )
    b = svc.create(
        tenant.id,
        name="Jane Doe",
        phone="+15551110004",
        email="jane@example.com",
    )
    cid_a = uuid.UUID(a["id"])
    svc.locations.create_location(
        tenant.id,
        cid_a,
        address_line_1="42 Willow Lane",
        city="Springfield",
        postal_code="62704",
    )

    phone = svc.search(tenant.id, q="(555) 111-0003")
    assert [c["id"] for c in phone["customers"]] == [a["id"]]
    phone_e164 = svc.search(tenant.id, q="+15551110003")
    assert [c["id"] for c in phone_e164["customers"]] == [a["id"]]

    email = svc.search(tenant.id, q="Jon.Smith@Example.com")
    assert [c["id"] for c in email["customers"]] == [a["id"]]

    name = svc.search(tenant.id, q="jonath")
    assert any(c["id"] == a["id"] for c in name["customers"])

    addr = svc.search(tenant.id, q="Willow")
    assert any(c["id"] == a["id"] for c in addr["customers"])

    page1 = svc.list(tenant.id, limit=1)
    assert len(page1["customers"]) == 1
    assert page1["next_cursor"]
    page2 = svc.list(tenant.id, limit=1, cursor=page1["next_cursor"])
    assert len(page2["customers"]) == 1
    assert page1["customers"][0]["id"] != page2["customers"][0]["id"]
    ids = {page1["customers"][0]["id"], page2["customers"][0]["id"]}
    assert a["id"] in ids and b["id"] in ids


def test_timeline_aggregates_existing_domains(session: Session, tenant: Tenant) -> None:
    svc = CustomerService(session)
    cust = svc.create(tenant.id, name="Timeline Cust", phone="+15551110005")
    cid = uuid.UUID(cust["id"])
    now = datetime.now(UTC)

    session.add(
        Call(
            tenant_id=tenant.id,
            customer_id=cid,
            room_name=f"room-{uuid.uuid4().hex[:8]}",
            started_at=now - timedelta(hours=2),
            status="ended",
        )
    )
    session.add(
        Lead(
            tenant_id=tenant.id,
            customer_id=cid,
            title="AC Repair",
            service_type="AC Repair",
            reference_code="JB-AAA111",
            status="NEW",
            source="PHONE",
            priority="MEDIUM",
            created_at=now - timedelta(hours=1),
        )
    )
    session.add(
        Appointment(
            tenant_id=tenant.id,
            customer_id=cid,
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=1),
            service_type="Tune-up",
            confirmation_code="CNF1",
        )
    )
    session.add(
        Job(
            tenant_id=tenant.id,
            customer_id=cid,
            job_number="JOB-000001",
            service_type="Install",
            reference_code="JB-BBB222",
            status="NEW",
            priority="MEDIUM",
            created_at=now - timedelta(minutes=30),
        )
    )
    session.flush()
    svc.add_note(tenant.id, cid, "Follow up next week", actor="tester")

    tl = svc.timeline(
        tenant.id,
        cid,
        allowed_permission_keys=frozenset(
            {
                "customers.read",
                "calls.read",
                "leads.read",
                "jobs.read",
                "appointments.read",
            }
        ),
        limit=50,
    )
    types = [item["type"] for item in tl["items"]]
    assert "CALL" in types
    assert "LEAD" in types
    assert "JOB" in types
    assert "APPOINTMENT" in types
    assert "NOTE" in types
    assert "ORDER" not in types
    assert "INVOICE" not in types

    # Permission filter: without calls.read, CALL omitted
    filtered = svc.timeline(
        tenant.id,
        cid,
        allowed_permission_keys=frozenset({"customers.read"}),
    )
    assert all(item["type"] == "NOTE" for item in filtered["items"])

    # Deterministic order: timestamps descending
    stamps = [item["timestamp"] for item in tl["items"]]
    assert stamps == sorted(stamps, reverse=True)


def test_tenant_isolation_idor(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    svc = CustomerService(session)
    a = svc.create(tenant.id, name="Tenant A Cust", phone="+15551110006")
    b = svc.create(tenant_b.id, name="Tenant B Cust", phone="+15551110007")
    a_id = uuid.UUID(a["id"])
    b_id = uuid.UUID(b["id"])

    assert svc.lookup_by_phone(tenant.id, "+15551110007") is None
    search = svc.search(tenant.id, q="Tenant B")
    assert all(c["id"] != b["id"] for c in search["customers"])

    with pytest.raises(CrmError) as exc:
        svc.get(tenant.id, b_id)
    assert exc.value.code == "not_found"

    with pytest.raises(CrmError):
        svc.update(tenant.id, b_id, name="Hacked")

    with pytest.raises(CrmError):
        svc.archive(tenant.id, b_id)

    with pytest.raises(CrmError):
        svc.locations.create_location(tenant.id, b_id, address_line_1="Cross tenant")

    with pytest.raises(CrmError):
        svc.locations.list_locations(tenant.id, b_id)

    with pytest.raises(CrmError):
        svc.timeline(
            tenant.id,
            b_id,
            allowed_permission_keys=frozenset({"customers.read"}),
        )

    with pytest.raises(CrmError):
        svc.add_tag(tenant.id, b_id, "stolen")

    # Location belonging to A cannot be accessed via B customer id
    loc = svc.locations.create_location(tenant.id, a_id, address_line_1="A Home")
    with pytest.raises(CrmError):
        svc.locations.get_location(tenant_b.id, a_id, uuid.UUID(loc["id"]))
    with pytest.raises(CrmError):
        svc.locations.update_location(
            tenant_b.id, b_id, uuid.UUID(loc["id"]), address_line_1="Nope"
        )


def test_duplicate_suggestions_not_merge(session: Session, tenant: Tenant) -> None:
    svc = CustomerService(session)
    a = svc.create(
        tenant.id,
        name="Dup One",
        phone="+15551110008",
        email="same@example.com",
    )
    b = svc.create(
        tenant.id,
        name="Dup Two",
        phone="+15551110009",
        email="same@example.com",
    )
    dups = svc.find_potential_duplicates(tenant.id, uuid.UUID(a["id"]))
    assert any(d["id"] == b["id"] for d in dups)
    assert "email" in dups[0]["signals"]
    # Still two distinct customers
    assert session.get(Customer, uuid.UUID(a["id"])) is not None
    assert session.get(Customer, uuid.UUID(b["id"])) is not None
