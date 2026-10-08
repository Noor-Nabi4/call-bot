"""Phase 24 Human Handoff: routing, emergency, context, assignment, isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.automations.constants import AutomationEventType
from callbot_platform.db.models import Call, Tenant
from callbot_platform.db.models.automations import AutomationEvent
from callbot_platform.db.models.human_handoff import HandoffAssignment
from callbot_platform.handoff.repos import HandoffRepository
from callbot_platform.human_handoff.constants import HandoffPriority, HandoffStatus
from callbot_platform.human_handoff.emergency import detect_emergency
from callbot_platform.human_handoff.errors import HandoffDomainError
from callbot_platform.human_handoff.service import HumanHandoffService
from callbot_platform.human_handoff.telephony import RecordingTransferProvider


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="HH Other", slug=f"hh-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _enable_handoff(session: Session, tenant_id: uuid.UUID) -> None:
    HandoffRepository(session).upsert(
        tenant_id,
        enabled=True,
        mode="warm",
        escalation_phone_e164="+15551230000",
        actor="t",
    )


def _call(session: Session, tenant_id: uuid.UUID) -> Call:
    call = Call(
        tenant_id=tenant_id,
        room_name=f"r-{uuid.uuid4().hex[:6]}",
        status="active",
        caller_number="+15551112222",
    )
    session.add(call)
    session.flush()
    return call


def test_emergency_detection_keywords_and_classification() -> None:
    assert detect_emergency(text="there is a water leak")["emergency"] is True
    assert detect_emergency(classification="EMERGENCY", classification_confidence=0.9)[
        "emergency"
    ]
    assert (
        detect_emergency(classification="EMERGENCY", classification_confidence=0.1)[
            "emergency"
        ]
        is False
    )
    assert detect_emergency(explicit_emergency=True)["emergency"] is True
    assert detect_emergency(text="hello")["emergency"] is False


def test_create_route_accept_complete_and_events(
    session: Session, tenant: Tenant
) -> None:
    _enable_handoff(session, tenant.id)
    call = _call(session, tenant.id)
    provider = RecordingTransferProvider()
    svc = HumanHandoffService(session, transfer_provider=provider)

    created = svc.create_request(
        tenant_id=tenant.id,
        channel="VOICE",
        actor="ai",
        reason="emergency",
        summary="Gas leak reported",
        emergency=True,
        call_id=call.id,
        idempotency_key=f"op-{uuid.uuid4().hex}",
    )
    assert created["priority"] == HandoffPriority.EMERGENCY.value
    assert created["status"] == HandoffStatus.ASSIGNED.value
    assert created["context_snapshot"]["emergency"]["emergency"] is True
    assert len(provider.calls) == 1

    key = f"idem-{uuid.uuid4().hex}"
    first = svc.create_request(
        tenant_id=tenant.id,
        channel="VOICE",
        actor="ai",
        reason="caller_request",
        summary="Need billing help",
        call_id=call.id,
        department="billing",
        idempotency_key=key,
    )
    second = svc.create_request(
        tenant_id=tenant.id,
        channel="VOICE",
        actor="ai",
        reason="caller_request",
        summary="Need billing help",
        call_id=call.id,
        department="billing",
        idempotency_key=key,
    )
    assert first["id"] == second["id"]

    accepted = svc.accept(tenant.id, uuid.UUID(first["id"]), actor="agent@test")
    assert accepted["status"] == HandoffStatus.CONNECTED.value

    completed = svc.complete(tenant.id, uuid.UUID(first["id"]), actor="agent@test")
    assert completed["status"] == HandoffStatus.COMPLETED.value

    events = {
        e.event_type
        for e in session.scalars(
            select(AutomationEvent).where(AutomationEvent.tenant_id == tenant.id)
        ).all()
    }
    assert AutomationEventType.HANDOFF_CREATED.value in events
    assert AutomationEventType.HANDOFF_ASSIGNED.value in events
    assert AutomationEventType.HANDOFF_CONNECTED.value in events
    assert AutomationEventType.HANDOFF_COMPLETED.value in events


def test_tenant_isolation_idor(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    _enable_handoff(session, tenant.id)
    _enable_handoff(session, tenant_b.id)
    call = _call(session, tenant.id)
    svc = HumanHandoffService(session)
    created = svc.create_request(
        tenant_id=tenant.id,
        channel="VOICE",
        actor="t",
        reason="complex",
        summary="Need help",
        call_id=call.id,
    )
    hid = uuid.UUID(created["id"])
    with pytest.raises(HandoffDomainError) as exc:
        svc.get(tenant_b.id, hid)
    assert exc.value.code == "handoff_not_found"
    with pytest.raises(HandoffDomainError):
        svc.accept(tenant_b.id, hid, actor="attacker")


def test_sms_handoff_channel(session: Session, tenant: Tenant) -> None:
    _enable_handoff(session, tenant.id)
    svc = HumanHandoffService(session)
    created = svc.create_request(
        tenant_id=tenant.id,
        channel="SMS",
        actor="sms_agent",
        reason="AI_REQUEST",
        summary="Customer asked for a person",
        department="support",
    )
    assert created["channel"] == "SMS"
    assert created["status"] == HandoffStatus.ASSIGNED.value


def test_reject_requeues(session: Session, tenant: Tenant) -> None:
    _enable_handoff(session, tenant.id)
    call = _call(session, tenant.id)
    svc = HumanHandoffService(session)
    created = svc.create_request(
        tenant_id=tenant.id,
        channel="VOICE",
        actor="t",
        reason="complex",
        summary="Help",
        call_id=call.id,
        target_user_id=uuid.uuid4(),
    )
    hid = uuid.UUID(created["id"])
    rejected = svc.reject(tenant.id, hid, actor="agent")
    assert rejected["status"] == HandoffStatus.ASSIGNED.value
    rows = list(
        session.scalars(
            select(HandoffAssignment).where(
                HandoffAssignment.tenant_id == tenant.id,
                HandoffAssignment.handoff_id == hid,
            )
        ).all()
    )
    assert len(rows) >= 2
    assert any(r.status == "REJECTED" for r in rows)
    assert any(r.status == "PENDING" and r.assignment_type == "QUEUE" for r in rows)


def test_disabled_voice_handoff(session: Session, tenant: Tenant) -> None:
    HandoffRepository(session).upsert(tenant.id, enabled=False, mode="cold", actor="t")
    svc = HumanHandoffService(session)
    with pytest.raises(HandoffDomainError) as exc:
        svc.create_request(
            tenant_id=tenant.id,
            channel="VOICE",
            actor="t",
            reason="complex",
            summary="x",
        )
    assert exc.value.code == "handoff_disabled"


def test_routing_department_technician_after_hours(
    session: Session, tenant: Tenant
) -> None:
    from callbot_platform.human_handoff.routing import HandoffRoutingService

    router = HandoffRoutingService(session)
    emergency = router.decide(
        tenant_id=tenant.id,
        snapshot={
            "emergency": {"emergency": True},
            "business_hours": {"after_hours": False},
        },
    )
    assert emergency.queue_key == "emergency"
    assert emergency.priority == HandoffPriority.EMERGENCY.value

    tech_id = uuid.uuid4()
    tech = router.decide(
        tenant_id=tenant.id,
        snapshot={
            "emergency": {"emergency": False},
            "business_hours": {"after_hours": False},
        },
        target_technician_id=tech_id,
    )
    assert tech.assignment_type == "TECHNICIAN"
    assert tech.target_technician_id == tech_id

    dept = router.decide(
        tenant_id=tenant.id,
        snapshot={
            "emergency": {"emergency": False},
            "business_hours": {"after_hours": False},
        },
        requested_department="billing",
    )
    assert dept.assignment_type == "DEPARTMENT"
    assert dept.department_slug == "billing"

    after = router.decide(
        tenant_id=tenant.id,
        snapshot={
            "emergency": {"emergency": False},
            "business_hours": {"after_hours": True},
        },
    )
    assert after.queue_key == "after_hours"
    assert after.reason == "AFTER_HOURS"

    default = router.decide(
        tenant_id=tenant.id,
        snapshot={
            "emergency": {"emergency": False},
            "business_hours": {"after_hours": False},
        },
    )
    assert default.queue_key == "default"


def test_departments_seed_and_hours(session: Session, tenant: Tenant) -> None:
    from datetime import UTC, datetime, timedelta

    from callbot_platform.db.models.scheduling import BusinessHoliday
    from callbot_platform.human_handoff.departments import DepartmentService
    from callbot_platform.human_handoff.hours import HandoffHoursService

    depts = DepartmentService(session).list(tenant.id)
    slugs = {d["slug"] for d in depts}
    assert {"sales", "support", "dispatch", "billing", "emergency"} <= slugs

    hours = HandoffHoursService(session)
    # Empty weekly hours → after hours
    status = hours.status_at(tenant.id, when=datetime.now(UTC))
    assert status["after_hours"] is True

    holiday = BusinessHoliday(
        tenant_id=tenant.id,
        holiday_date=(datetime.now(UTC) + timedelta(days=0)).date(),
        name="Test Day",
    )
    session.add(holiday)
    session.flush()
    h_status = hours.status_at(tenant.id, when=datetime.now(UTC))
    assert h_status["holiday"] is True
    assert h_status["after_hours"] is True


def test_list_queue_views(session: Session, tenant: Tenant) -> None:
    _enable_handoff(session, tenant.id)
    svc = HumanHandoffService(session)
    svc.create_request(
        tenant_id=tenant.id,
        channel="VOICE",
        actor="t",
        reason="emergency",
        summary="Flood",
        emergency=True,
    )
    svc.create_request(
        tenant_id=tenant.id,
        channel="SMS",
        actor="t",
        reason="AI_REQUEST",
        summary="Normal",
        department="support",
    )
    queue = svc.list(tenant.id, status="QUEUE")
    assert len(queue["items"]) >= 2
    emergency = svc.list(tenant.id, status="EMERGENCY")
    assert all(i["priority"] == "EMERGENCY" for i in emergency["items"])
    assert len(emergency["items"]) >= 1


def test_sms_handoff_pauses_conversation(session: Session, tenant: Tenant) -> None:
    from callbot_platform.db.models.sms import SmsConversation
    from callbot_platform.human_handoff.sms import SmsHandoffService

    _enable_handoff(session, tenant.id)
    convo = SmsConversation(
        tenant_id=tenant.id,
        phone_e164="+15559876543",
        business_phone_e164="+15551230000",
        status="ACTIVE",
        workflow_state={},
    )
    session.add(convo)
    session.flush()
    SmsHandoffService(session).request(
        tenant_id=tenant.id,
        actor="sms",
        reason="CUSTOMER_REQUEST",
        summary="Need human",
        conversation_id=convo.id,
        department="support",
    )
    session.refresh(convo)
    assert convo.status == "HANDOFF"
