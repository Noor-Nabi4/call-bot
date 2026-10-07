"""Phase 21 Equipment: CRUD, warranty, serial, jobs, history, tenant isolation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.equipment import EquipmentService
from callbot_platform.crm.equipment.constants import WarrantyStatus
from callbot_platform.crm.equipment.warranty import EquipmentWarrantyService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs import JobService
from callbot_platform.crm.jobs.notes import JobNotesService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.equipment import Equipment


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Equip Other", slug=f"eq-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _customer_with_location(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Homeowner",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    location = CustomerService(session).locations.create_location(
        tenant_id,
        uuid.UUID(customer["id"]),
        address_line_1="1 Oak St",
        city="Austin",
        state="TX",
        postal_code="78701",
        actor="t",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "location_id": uuid.UUID(location["id"]),
    }


def test_equipment_crud_warranty_and_serial(session: Session, tenant: Tenant) -> None:
    ctx = _customer_with_location(session, tenant.id)
    svc = EquipmentService(session)
    today = datetime.now(UTC).date()
    created = svc.create(
        tenant.id,
        customer_id=ctx["customer_id"],
        manufacturer="Carrier",
        model="ABC-2400",
        actor="t",
        location_id=ctx["location_id"],
        serial_number=" ca-92838172 ",
        installation_date=today - timedelta(days=30),
        warranty_start_date=today - timedelta(days=30),
        warranty_end_date=today + timedelta(days=335),
        warranty_provider="Carrier",
        status="ACTIVE",
    )
    assert created["serial_number"] == "ca-92838172"
    assert created["warranty_status"] == WarrantyStatus.ACTIVE.value
    assert created["under_warranty"] is True

    listed = svc.list(tenant.id, serial_number="CA-92838172")
    assert len(listed["equipment"]) == 1

    updated = svc.update(
        tenant.id,
        uuid.UUID(created["id"]),
        actor="t",
        manufacturer="Carrier",
        model="ABC-2400-X",
    )
    assert updated["model"] == "ABC-2400-X"

    with pytest.raises(CrmError) as dup:
        svc.create(
            tenant.id,
            customer_id=ctx["customer_id"],
            manufacturer="Other",
            model="X",
            actor="t",
            serial_number="CA-92838172",
        )
    assert dup.value.code == "serial_conflict"


def test_warranty_states_and_invalid_dates(session: Session, tenant: Tenant) -> None:
    ctx = _customer_with_location(session, tenant.id)
    svc = EquipmentService(session)
    today = datetime.now(UTC).date()

    unknown = svc.create(
        tenant.id,
        customer_id=ctx["customer_id"],
        manufacturer="Lennox",
        model="M1",
        actor="t",
    )
    assert unknown["warranty_status"] == WarrantyStatus.UNKNOWN.value

    expired = svc.create(
        tenant.id,
        customer_id=ctx["customer_id"],
        manufacturer="Lennox",
        model="M2",
        actor="t",
        warranty_start_date=today - timedelta(days=400),
        warranty_end_date=today - timedelta(days=10),
    )
    assert expired["warranty_status"] == WarrantyStatus.EXPIRED.value

    with pytest.raises(CrmError) as bad:
        svc.create(
            tenant.id,
            customer_id=ctx["customer_id"],
            manufacturer="Lennox",
            model="M3",
            actor="t",
            warranty_start_date=today,
            warranty_end_date=today - timedelta(days=1),
        )
    assert bad.value.code == "invalid_warranty_dates"

    row = session.get(Equipment, uuid.UUID(expired["id"]))
    assert row is not None
    assert EquipmentWarrantyService.is_under_warranty(row, at=today) is False


def test_tenant_isolation_and_location_mismatch(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    ctx_a = _customer_with_location(session, tenant.id)
    other_customer = CustomerService(session).create(
        tenant.id,
        name="Neighbor",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    other_loc = CustomerService(session).locations.create_location(
        tenant.id,
        uuid.UUID(other_customer["id"]),
        address_line_1="2 Pine St",
        city="Austin",
        state="TX",
        postal_code="78702",
        actor="t",
    )
    svc = EquipmentService(session)
    eq = svc.create(
        tenant.id,
        customer_id=ctx_a["customer_id"],
        manufacturer="Trane",
        model="T1",
        actor="t",
        location_id=ctx_a["location_id"],
    )
    eid = uuid.UUID(eq["id"])

    with pytest.raises(CrmError):
        svc.get(tenant_b.id, eid)

    with pytest.raises(CrmError) as loc:
        svc.create(
            tenant.id,
            customer_id=ctx_a["customer_id"],
            manufacturer="Trane",
            model="T2",
            actor="t",
            location_id=uuid.UUID(other_loc["id"]),
        )
    assert loc.value.code == "location_customer_mismatch"


def test_job_equipment_link_and_history(
    session: Session, tenant: Tenant
) -> None:
    ctx = _customer_with_location(session, tenant.id)
    service = ServicesPricebookService(session).create_service(
        tenant.id, name="Tune-up", actor="t"
    )
    today = datetime.now(UTC).date()
    eq = EquipmentService(session).create(
        tenant.id,
        customer_id=ctx["customer_id"],
        manufacturer="Goodman",
        model="G1",
        actor="t",
        location_id=ctx["location_id"],
        serial_number=f"SN-{uuid.uuid4().hex[:8]}",
        installation_date=today,
    )
    jobs = JobService(session)
    job = jobs.create(
        tenant.id,
        customer_id=ctx["customer_id"],
        actor="t",
        service_id=uuid.UUID(service["id"]),
        location_id=ctx["location_id"],
        equipment_id=uuid.UUID(eq["id"]),
        description="Annual service",
    )
    assert job["equipment_id"] == eq["id"]

    JobNotesService(session).create(
        tenant.id, uuid.UUID(job["id"]), body="Filter replaced", actor="t"
    )

    hist = EquipmentService(session).history.history(
        tenant.id, uuid.UUID(eq["id"]), limit=50, offset=0
    )
    types = {item["type"] for item in hist["history"]}
    assert "INSTALLATION" in types or "WARRANTY" in types
    assert "SERVICE" in types
    assert "TECHNICIAN_NOTE" in types

    other = CustomerService(session).create(
        tenant.id,
        name="Other owner",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    with pytest.raises(CrmError) as mismatch:
        jobs.create(
            tenant.id,
            customer_id=uuid.UUID(other["id"]),
            actor="t",
            equipment_id=uuid.UUID(eq["id"]),
            service_type="Repair",
        )
    assert mismatch.value.code == "equipment_customer_mismatch"


def test_archive_with_jobs_vs_without(session: Session, tenant: Tenant) -> None:
    ctx = _customer_with_location(session, tenant.id)
    svc = EquipmentService(session)
    eq = svc.create(
        tenant.id,
        customer_id=ctx["customer_id"],
        manufacturer="Rheem",
        model="R1",
        actor="t",
        serial_number=f"R-{uuid.uuid4().hex[:8]}",
    )
    eid = uuid.UUID(eq["id"])

    deleted = svc.delete(tenant.id, eid, actor="t")
    assert deleted.get("deleted") is True

    eq2 = svc.create(
        tenant.id,
        customer_id=ctx["customer_id"],
        manufacturer="Rheem",
        model="R2",
        actor="t",
        serial_number=f"R2-{uuid.uuid4().hex[:8]}",
        location_id=ctx["location_id"],
    )
    JobService(session).create(
        tenant.id,
        customer_id=ctx["customer_id"],
        actor="t",
        equipment_id=uuid.UUID(eq2["id"]),
        service_type="Inspect",
        location_id=ctx["location_id"],
    )
    archived = svc.delete(tenant.id, uuid.UUID(eq2["id"]), actor="t")
    assert archived.get("deleted") is not True
    assert archived["status"] == "REMOVED"
