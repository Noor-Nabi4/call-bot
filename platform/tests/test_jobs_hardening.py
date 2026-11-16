"""Phase 10 Jobs hardening: fingerprint, schedule, matrix, N+1, attachments."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs import JobService
from callbot_platform.crm.jobs.attachments import JobAttachmentService
from callbot_platform.crm.jobs.constants import (
    CANCELLABLE_STATUSES,
    EDITABLE_STATUSES,
    JOB_STATUSES,
    NO_SHOW_FROM,
    VALID_TRANSITIONS,
    JobStatus,
)
from callbot_platform.crm.jobs.fingerprint import job_create_fingerprint
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import TelephonyAuditEvent, Tenant
from callbot_platform.db.models.jobs import JobStatusHistory
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


def test_idempotency_fingerprint_conflict(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_type="Install",
        idempotency_key="hard-1",
    )
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_type="Repair",
            idempotency_key="hard-1",
        )
    assert exc.value.code == "idempotency_conflict"


def test_idempotency_same_fingerprint_returns_same(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    kwargs = {
        "customer_id": setup["customer_id"],
        "service_id": setup["service_id"],
        "location_id": setup["location_id"],
        "priority": "HIGH",
        "description": "Same payload",
        "idempotency_key": "hard-same",
    }
    a = api.create(tenant.id, actor="t", **kwargs)
    b = api.create(tenant.id, actor="t", **kwargs)
    assert a["id"] == b["id"]


def test_fingerprint_stable_and_sensitive() -> None:
    cid = uuid.uuid4()
    base = {
        "customer_id": cid,
        "service_id": None,
        "service_type": "Install",
        "location_id": None,
        "description": None,
        "priority": "MEDIUM",
        "technician_id": None,
        "scheduled_starts_at": None,
        "scheduled_ends_at": None,
        "appointment_id": None,
        "lead_id": None,
        "call_id": None,
        "status": "NEW",
    }
    a = job_create_fingerprint(**base)
    b = job_create_fingerprint(**base)
    assert a == b
    changed = {**base, "service_type": "Repair"}
    assert job_create_fingerprint(**changed) != a


def test_schedule_validation(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    start = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    end = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_id=setup["service_id"],
            scheduled_starts_at=start,
            scheduled_ends_at=end,
        )
    assert exc.value.code == "invalid_schedule"

    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_id=setup["service_id"],
            scheduled_starts_at=start,
            scheduled_ends_at=start,
        )
    assert exc.value.code == "invalid_schedule"

    ok = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        scheduled_starts_at=start,
        scheduled_ends_at=start + timedelta(hours=2),
    )
    assert ok["scheduled_starts_at"] is not None

    only_start = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_type="Only start",
        scheduled_starts_at=start,
    )
    assert only_start["scheduled_ends_at"] is None


def test_editable_statuses_enforced(session: Session, tenant: Tenant) -> None:
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
    assert "DISPATCHED" not in EDITABLE_STATUSES
    with pytest.raises(CrmError) as exc:
        api.update(tenant.id, jid, description="mutate after dispatch", actor="t")
    assert exc.value.code == "job_immutable"


def test_unassign_blocked_outside_assignable(session: Session, tenant: Tenant) -> None:
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
    api.transition(tenant.id, jid, to_status="IN_PROGRESS", actor="t")
    with pytest.raises(CrmError) as exc:
        api.assign(tenant.id, jid, technician_id=None, actor="t")
    assert exc.value.code == "invalid_transition"


def test_full_happy_path_and_invalid_matrix(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        status="NEW",
    )
    jid = uuid.UUID(job["id"])
    path = [
        "SCHEDULED",
        "CONFIRMED",
        "DISPATCHED",
        "EN_ROUTE",
        "ARRIVED",
        "IN_PROGRESS",
        "COMPLETED",
    ]
    api.assign(tenant.id, jid, technician_id=setup["technician_id"], actor="t")
    for to in path:
        kwargs: dict = {"to_status": to, "actor": "t"}
        if to == "COMPLETED":
            kwargs["completion_notes"] = "All good"
        api.transition(tenant.id, jid, **kwargs)

    history = api.history(tenant.id, jid)
    assert [h["to_status"] for h in history] == ["NEW", *path]

    for bad in ("CANCELLED", "NO_SHOW", "IN_PROGRESS", "NEW"):
        with pytest.raises(CrmError) as exc:
            api.transition(tenant.id, jid, to_status=bad, actor="t")
        assert exc.value.code == "invalid_transition"

    asserted: set[tuple[str, str]] = set()
    for src in JOB_STATUSES:
        for dst in JOB_STATUSES:
            if src == dst:
                continue
            if (src, dst) in VALID_TRANSITIONS:
                asserted.add((src, dst))
    assert frozenset(asserted) == VALID_TRANSITIONS


def test_cancel_matrix_and_no_show_from(session: Session, tenant: Tenant) -> None:
    assert frozenset(
        {
            JobStatus.NEW.value,
            JobStatus.SCHEDULED.value,
            JobStatus.CONFIRMED.value,
            JobStatus.DISPATCHED.value,
            JobStatus.EN_ROUTE.value,
            JobStatus.ARRIVED.value,
            JobStatus.IN_PROGRESS.value,
        }
    ) == CANCELLABLE_STATUSES
    assert frozenset(
        {
            JobStatus.SCHEDULED.value,
            JobStatus.CONFIRMED.value,
            JobStatus.DISPATCHED.value,
            JobStatus.EN_ROUTE.value,
            JobStatus.ARRIVED.value,
        }
    ) == NO_SHOW_FROM
    setup = _setup(session, tenant.id)
    api = JobService(session)

    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
    )
    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, uuid.UUID(job["id"]), to_status="NO_SHOW", actor="t")
    assert exc.value.code == "invalid_transition"

    job2 = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        status="SCHEDULED",
    )
    jid2 = uuid.UUID(job2["id"])
    api.assign(tenant.id, jid2, technician_id=setup["technician_id"], actor="t")
    api.transition(tenant.id, jid2, to_status="DISPATCHED", actor="t")
    api.transition(tenant.id, jid2, to_status="IN_PROGRESS", actor="t")
    api.transition(
        tenant.id,
        jid2,
        to_status="COMPLETED",
        actor="t",
        completion_notes="done",
    )
    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, jid2, to_status="CANCELLED", actor="t")
    assert exc.value.code == "invalid_transition"


def test_invalid_transition_no_history_or_success_audit(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    job = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
    )
    jid = uuid.UUID(job["id"])
    hist_count = len(
        list(
            session.scalars(
                select(JobStatusHistory).where(JobStatusHistory.job_id == jid)
            ).all()
        )
    )
    audits_before = len(
        list(
            session.scalars(
                select(TelephonyAuditEvent).where(
                    TelephonyAuditEvent.tenant_id == tenant.id,
                    TelephonyAuditEvent.action == "job_status_changed",
                )
            ).all()
        )
    )
    with pytest.raises(CrmError):
        api.transition(tenant.id, jid, to_status="COMPLETED", actor="t")
    hist_after = len(
        list(
            session.scalars(
                select(JobStatusHistory).where(JobStatusHistory.job_id == jid)
            ).all()
        )
    )
    audits_after = len(
        list(
            session.scalars(
                select(TelephonyAuditEvent).where(
                    TelephonyAuditEvent.tenant_id == tenant.id,
                    TelephonyAuditEvent.action == "job_status_changed",
                )
            ).all()
        )
    )
    assert hist_after == hist_count
    assert audits_after == audits_before


def test_attachment_mime_mismatch_rejected(session: Session, tenant: Tenant) -> None:
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
            filename="evil.jpg",
            content_type="image/jpeg",
            data=b"not-a-jpeg",
            actor="t",
        )
    assert exc.value.code == "invalid_content_type"

    uploaded = attachments.upload(
        tenant.id,
        jid,
        filename="../../etc/passwd.txt",
        content_type="text/plain",
        data=b"hello notes",
        actor="t",
    )
    assert ".." not in uploaded["filename"]
    assert uploaded["filename"] == "passwd.txt"


def test_attachment_cross_tenant(
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
    attachments = JobAttachmentService(session)
    uploaded = attachments.upload(
        tenant.id,
        uuid.UUID(job_a["id"]),
        filename="a.jpg",
        content_type="image/jpeg",
        data=b"\xff\xd8\xff\xe0fakejpegdata",
        actor="t",
    )
    with pytest.raises(CrmError):
        attachments.list(tenant_b.id, uuid.UUID(job_a["id"]))
    with pytest.raises(CrmError):
        attachments.archive(
            tenant_b.id,
            uuid.UUID(job_a["id"]),
            uuid.UUID(uploaded["id"]),
            actor="t",
        )
    with pytest.raises(CrmError):
        attachments.upload(
            tenant_b.id,
            uuid.UUID(job_a["id"]),
            filename="b.jpg",
            content_type="image/jpeg",
            data=b"\xff\xd8\xff\xe0fakejpegdata",
            actor="t",
        )
    # Unused setup_b ensures tenant B scaffolding exists for isolation.
    assert setup_b["customer_id"] != setup_a["customer_id"]


def test_list_n_plus_one_bounded(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    for _ in range(25):
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_id=setup["service_id"],
        )

    engine = session.get_bind()
    assert isinstance(engine, Engine)
    queries: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        result = api.list(tenant.id, limit=20)
        assert len(result["jobs"]) == 20
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert len(queries) < 15, f"too many queries: {len(queries)}"


def test_keyset_pagination_stable(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = JobService(session)
    ids: list[str] = []
    for _ in range(7):
        row = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_type=f"svc-{uuid.uuid4().hex[:4]}",
        )
        ids.append(row["id"])

    page1 = api.list(tenant.id, limit=3)
    assert len(page1["jobs"]) == 3
    assert page1["next_cursor"]
    page2 = api.list(tenant.id, limit=3, cursor=page1["next_cursor"])
    assert len(page2["jobs"]) == 3
    page3 = api.list(tenant.id, limit=3, cursor=page2["next_cursor"])
    seen = [j["id"] for j in page1["jobs"] + page2["jobs"] + page3["jobs"]]
    assert len(seen) == len(set(seen))
    assert set(seen) == set(ids)


def test_cross_tenant_reference_on_assign(
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
    with pytest.raises(CrmError) as exc:
        api.assign(
            tenant.id,
            uuid.UUID(job["id"]),
            technician_id=setup_b["technician_id"],
            actor="t",
        )
    assert exc.value.code == "technician_not_found"
