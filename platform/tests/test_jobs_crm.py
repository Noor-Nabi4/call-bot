"""Phase 10 Jobs: CRUD, relations, lifecycle, notes, attachments, isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.customers.timeline import CustomerTimelineService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs import JobService
from callbot_platform.crm.jobs.attachments import JobAttachmentService
from callbot_platform.crm.jobs.notes import JobNotesService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.jobs import JobNumberCounter, Technician
from callbot_platform.jobs.repos import TechnicianRepository


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _setup(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    location = CustomerService(session).locations.create_location(
        tenant_id,
        uuid.UUID(customer["id"]),
        address_line_1="123 Main St",
        city="Austin",
        state="TX",
        postal_code="78701",
        actor="t",
    )
    service = ServicesPricebookService(session).create_service(
        tenant_id, name="AC Repair", actor="t"
    )
    tech = TechnicianRepository(session).create(
        tenant_id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Tech One",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "location_id": uuid.UUID(location["id"]),
        "service_id": uuid.UUID(service["id"]),
        "technician_id": uuid.UUID(tech["id"]),
    }


def test_job_crud_relations_search_archive(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        location_id=setup["location_id"],
        description="Fix the unit",
        priority="HIGH",
    )
    assert created["job_number"] == "JOB-000001"
    assert created["status"] == "NEW"
    assert created["priority"] == "HIGH"
    assert created["service"]["id"] == str(setup["service_id"])
    assert created["location"]["id"] == str(setup["location_id"])
    assert created["customer"]["id"] == str(setup["customer_id"])

    found = api.list(tenant.id, q="JOB-000001")
    assert len(found["jobs"]) == 1
    found = api.list(tenant.id, status="NEW", customer_id=setup["customer_id"])
    assert len(found["jobs"]) == 1
    found = api.list(tenant.id, priority="HIGH")
    assert len(found["jobs"]) == 1
    found = api.list(tenant.id, location_id=setup["location_id"])
    assert len(found["jobs"]) == 1
    found = api.list(tenant.id, service_id=setup["service_id"])
    assert len(found["jobs"]) == 1

    updated = api.update(
        tenant.id,
        uuid.UUID(created["id"]),
        description="Updated description",
        priority="URGENT",
        actor="t",
    )
    assert updated["description"] == "Updated description"
    assert updated["priority"] == "URGENT"

    archived = api.archive(tenant.id, uuid.UUID(created["id"]), actor="t")
    assert archived["archived_at"] is not None
    restored = api.restore(tenant.id, uuid.UUID(created["id"]), actor="t")
    assert restored["archived_at"] is None


def test_idempotent_create(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    a = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_type="Install",
        idempotency_key="idem-1",
    )
    b = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_type="Install",
        idempotency_key="idem-1",
    )
    assert a["id"] == b["id"]


def test_create_requires_service(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    with pytest.raises(CrmError) as exc:
        api.create(tenant.id, customer_id=setup["customer_id"], actor="t")
    assert exc.value.code == "service_required"


def test_create_only_new_or_scheduled(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_type="Install",
            status="COMPLETED",
        )
    assert exc.value.code == "invalid_status"


def test_status_machine_and_history(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        status="SCHEDULED",
    )
    jid = uuid.UUID(job["id"])

    with pytest.raises(CrmError) as exc:
        api.update(tenant.id, jid, status="CONFIRMED", actor="t")
    assert exc.value.code == "use_transition"

    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, jid, to_status="COMPLETED", actor="t")
    assert exc.value.code == "invalid_transition"

    api.assign(tenant.id, jid, technician_id=setup["technician_id"], actor="t")
    api.transition(tenant.id, jid, to_status="DISPATCHED", actor="t")
    api.transition(tenant.id, jid, to_status="IN_PROGRESS", actor="t")

    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, jid, to_status="COMPLETED", actor="t")
    assert exc.value.code == "completion_notes_required"

    done = api.transition(
        tenant.id,
        jid,
        to_status="COMPLETED",
        actor="t",
        completion_notes="Replaced capacitor",
    )
    assert done["status"] == "COMPLETED"
    assert done["completion_notes"] == "Replaced capacitor"

    history = api.history(tenant.id, jid)
    to_statuses = [h["to_status"] for h in history]
    assert to_statuses == ["SCHEDULED", "DISPATCHED", "IN_PROGRESS", "COMPLETED"]


def test_requires_technician_before_dispatch(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        status="SCHEDULED",
    )
    jid = uuid.UUID(job["id"])
    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, jid, to_status="DISPATCHED", actor="t")
    assert exc.value.code == "technician_required"


def test_cancel_and_no_show_paths(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        status="SCHEDULED",
    )
    jid = uuid.UUID(job["id"])
    cancelled = api.transition(
        tenant.id, jid, to_status="CANCELLED", actor="t", reason="customer request"
    )
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["cancelled_at"] is not None

    job2 = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        status="SCHEDULED",
    )
    jid2 = uuid.UUID(job2["id"])
    no_show = api.transition(tenant.id, jid2, to_status="NO_SHOW", actor="t")
    assert no_show["status"] == "NO_SHOW"

    # Only NEW/COMPLETED/CANCELLED/NO_SHOW are archivable.
    archived = api.archive(tenant.id, jid, actor="t")
    assert archived["archived_at"] is not None


def test_archive_not_allowed_mid_flow(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        status="SCHEDULED",
    )
    jid = uuid.UUID(job["id"])
    api.assign(tenant.id, jid, technician_id=setup["technician_id"], actor="t")
    api.transition(tenant.id, jid, to_status="DISPATCHED", actor="t")
    with pytest.raises(CrmError) as exc:
        api.archive(tenant.id, jid, actor="t")
    assert exc.value.code == "archive_not_allowed"


def test_assign_unassign(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
    )
    jid = uuid.UUID(job["id"])
    assigned = api.assign(
        tenant.id, jid, technician_id=setup["technician_id"], actor="t"
    )
    assert assigned["assigned_technician_id"] == str(setup["technician_id"])
    unassigned = api.assign(tenant.id, jid, technician_id=None, actor="t")
    assert unassigned["assigned_technician_id"] is None


def test_notes_crud(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
    )
    jid = uuid.UUID(job["id"])
    notes = JobNotesService(session)
    note = notes.create(tenant.id, jid, body="On site now", actor="t")
    assert note["body"] == "On site now"

    updated = notes.update(
        tenant.id, jid, uuid.UUID(note["id"]), body="On site, diagnosing", actor="t"
    )
    assert updated["body"] == "On site, diagnosing"

    listed = notes.list(tenant.id, jid)
    assert len(listed) == 1

    archived = notes.archive(tenant.id, jid, uuid.UUID(note["id"]), actor="t")
    assert archived["archived_at"] is not None
    assert notes.list(tenant.id, jid) == []
    assert len(notes.list(tenant.id, jid, include_archived=True)) == 1


def test_notes_validation(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
    )
    jid = uuid.UUID(job["id"])
    notes = JobNotesService(session)
    with pytest.raises(CrmError) as exc:
        notes.create(tenant.id, jid, body="   ", actor="t")
    assert exc.value.code == "invalid_note"


def test_attachments_upload_list_archive(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
    )
    jid = uuid.UUID(job["id"])
    attachments = JobAttachmentService(session)
    uploaded = attachments.upload(
        tenant.id,
        jid,
        filename="before.jpg",
        content_type="image/jpeg",
        data=b"\xff\xd8\xff\xe0fakejpegdata",
        actor="t",
    )
    assert uploaded["filename"] == "before.jpg"
    assert uploaded["download_url"]

    listed = attachments.list(tenant.id, jid)
    assert len(listed) == 1

    archived = attachments.archive(tenant.id, jid, uuid.UUID(uploaded["id"]), actor="t")
    assert archived["archived_at"] is not None
    assert attachments.list(tenant.id, jid) == []


def test_attachment_empty_file_rejected(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
    )
    jid = uuid.UUID(job["id"])
    attachments = JobAttachmentService(session)
    with pytest.raises(CrmError) as exc:
        attachments.upload(
            tenant.id,
            jid,
            filename="empty.jpg",
            content_type="image/jpeg",
            data=b"",
            actor="t",
        )
    assert exc.value.code == "invalid_attachment"


def test_location_must_belong_to_customer(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    other_customer = CustomerService(session).create(
        tenant.id, name="Other Buyer", phone="+15559990001", actor="t"
    )
    other_location = CustomerService(session).locations.create_location(
        tenant.id,
        uuid.UUID(other_customer["id"]),
        address_line_1="999 Other Ave",
        actor="t",
    )
    api = JobService(session)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_id=setup["service_id"],
            location_id=uuid.UUID(other_location["id"]),
        )
    assert exc.value.code == "location_customer_mismatch"


def test_cross_tenant_isolation(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    setup_a = _setup(session, tenant.id)
    setup_b = _setup(session, tenant_b.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup_a["customer_id"],
        actor="t",
        service_id=setup_a["service_id"],
    )
    jid = uuid.UUID(job["id"])
    with pytest.raises(CrmError):
        api.get(tenant_b.id, jid)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup_b["customer_id"],
            actor="t",
            service_id=setup_a["service_id"],
        )
    assert exc.value.code == "customer_not_found"
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup_a["customer_id"],
            actor="t",
            service_id=setup_b["service_id"],
        )
    assert exc.value.code == "service_not_found"


def test_job_number_counter_is_tenant_scoped(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    setup_a = _setup(session, tenant.id)
    setup_b = _setup(session, tenant_b.id)
    api = JobService(session)
    job_a = api.create(
        tenant.id,
        customer_id=setup_a["customer_id"],
        actor="t",
        service_id=setup_a["service_id"],
    )
    job_b = api.create(
        tenant_b.id,
        customer_id=setup_b["customer_id"],
        actor="t",
        service_id=setup_b["service_id"],
    )
    assert job_a["job_number"] == "JOB-000001"
    assert job_b["job_number"] == "JOB-000001"
    counters = list(session.scalars(select(JobNumberCounter)).all())
    assert len(counters) == 2


def test_customer_timeline_job_events(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        status="SCHEDULED",
    )
    jid = uuid.UUID(job["id"])
    api.assign(tenant.id, jid, technician_id=setup["technician_id"], actor="t")
    api.transition(tenant.id, jid, to_status="DISPATCHED", actor="t")

    timeline = CustomerTimelineService(session).get_timeline(
        tenant.id,
        setup["customer_id"],
        allowed_types=frozenset({"JOB"}),
    )
    events = {i["metadata"].get("event") for i in timeline["items"]}
    assert "JOB_CREATED" in events
    assert "JOB_DISPATCHED" in events


def test_technician_not_found_cross_tenant(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    setup_a = _setup(session, tenant.id)
    setup_b = _setup(session, tenant_b.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup_a["customer_id"],
        actor="t",
        service_id=setup_a["service_id"],
    )
    jid = uuid.UUID(job["id"])
    with pytest.raises(CrmError) as exc:
        api.assign(tenant.id, jid, technician_id=setup_b["technician_id"], actor="t")
    assert exc.value.code == "technician_not_found"

    tech_b_row = session.scalar(
        select(Technician).where(Technician.id == setup_b["technician_id"])
    )
    assert tech_b_row is not None
