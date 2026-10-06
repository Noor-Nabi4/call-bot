"""Phase 11 Appointments: hours, holidays, create, fingerprint, transitions,
availability engine (skills/service area), location integrity.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.appointments.constants import normalize_status
from callbot_platform.crm.appointments.engine import AvailabilityEngine
from callbot_platform.crm.appointments.hours import (
    BusinessHoursService,
    validate_weekly_hours,
)
from callbot_platform.crm.appointments.service import AppointmentService
from callbot_platform.crm.appointments.technician_availability import (
    TechnicianAvailabilityService,
)
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Tenant
from callbot_platform.jobs.repos import TechnicianRepository


def _setup(session: Session, tenant_id: uuid.UUID, **service_kwargs) -> dict:
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
        tenant_id, name="AC Repair", actor="t", **service_kwargs
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


def _next_monday_9am() -> datetime:
    now = datetime.now(UTC)
    days_ahead = (7 - now.weekday()) % 7 or 7
    day = (now + timedelta(days=days_ahead)).date()
    return datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)


# --- Hours ---


def test_validate_weekly_hours_ok() -> None:
    cleaned = validate_weekly_hours(
        {"mon": [["09:00", "12:00"], ["13:00", "17:00"]], "sat": []}
    )
    assert cleaned["mon"] == [["09:00", "12:00"], ["13:00", "17:00"]]
    assert cleaned["sun"] == []


def test_validate_weekly_hours_rejects_overlap() -> None:
    with pytest.raises(CrmError) as exc:
        validate_weekly_hours({"mon": [["09:00", "13:00"], ["12:00", "17:00"]]})
    assert exc.value.code == "invalid_weekly_hours"


def test_validate_weekly_hours_rejects_bad_order() -> None:
    with pytest.raises(CrmError):
        validate_weekly_hours({"mon": [["17:00", "09:00"]]})


def test_validate_weekly_hours_rejects_unknown_day() -> None:
    with pytest.raises(CrmError):
        validate_weekly_hours({"funday": [["09:00", "17:00"]]})


def test_business_hours_update_and_holidays(session: Session, tenant: Tenant) -> None:
    svc = BusinessHoursService(session)
    updated = svc.update(
        tenant.id,
        actor="t",
        timezone="America/Chicago",
        slot_minutes=30,
        weekly_hours={"mon": [["08:00", "16:00"]]},
        emergency_weekly_hours={"mon": [["00:00", "23:59"]]},
    )
    assert updated["slot_minutes"] == 30
    assert updated["timezone"] == "America/Chicago"
    assert updated["weekly_hours"]["mon"] == [["08:00", "16:00"]]

    holiday = svc.create_holiday(
        tenant.id,
        holiday_date=datetime(2030, 12, 25).date(),
        name="Christmas",
        actor="t",
    )
    assert holiday["name"] == "Christmas"
    listed = svc.list_holidays(tenant.id)
    assert len(listed) == 1

    with pytest.raises(CrmError) as exc:
        svc.create_holiday(
            tenant.id, holiday_date=datetime(2030, 12, 25).date(), name="Dup", actor="t"
        )
    assert exc.value.code == "holiday_conflict"

    svc.delete_holiday(tenant.id, uuid.UUID(holiday["id"]), actor="t")
    assert svc.list_holidays(tenant.id) == []


def test_business_hours_invalid_timezone_rejected(
    session: Session, tenant: Tenant
) -> None:
    with pytest.raises(CrmError) as exc:
        BusinessHoursService(session).update(tenant.id, actor="t", timezone="Not/AZone")
    assert exc.value.code == "invalid_timezone"


# --- Create / fingerprint / location integrity ---


def test_appointment_create_basic(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id, duration_minutes=45)
    api = AppointmentService(session)
    starts = _next_monday_9am()
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_id=setup["service_id"],
        location_id=setup["location_id"],
        technician_id=setup["technician_id"],
    )
    assert created["appointment_number"] == "APT-000001"
    assert created["status"] == "SCHEDULED"
    assert created["duration_minutes"] == 45
    assert created["service"]["id"] == str(setup["service_id"])
    assert created["location"]["id"] == str(setup["location_id"])
    assert created["assigned_technician_id"] == str(setup["technician_id"])

    found = api.list(tenant.id, q="APT-000001")
    assert len(found["appointments"]) == 1
    found = api.list(tenant.id, customer_id=setup["customer_id"])
    assert len(found["appointments"]) == 1
    found = api.list(tenant.id, technician_id=setup["technician_id"])
    assert len(found["appointments"]) == 1


def test_appointment_create_requires_service_type(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = AppointmentService(session)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=_next_monday_9am(),
            actor="t",
        )
    assert exc.value.code == "service_required"


def test_appointment_idempotent_create(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = AppointmentService(session)
    starts = _next_monday_9am()
    a = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_type="Install",
        idempotency_key="idem-1",
    )
    b = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_type="Install",
        idempotency_key="idem-1",
    )
    assert a["id"] == b["id"]


def test_appointment_idempotency_fingerprint_conflict(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = AppointmentService(session)
    starts = _next_monday_9am()
    api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_type="Install",
        idempotency_key="fp-conflict",
    )
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts + timedelta(hours=1),
            actor="t",
            service_type="Repair",
            idempotency_key="fp-conflict",
        )
    assert exc.value.code == "idempotency_conflict"


def test_appointment_location_must_belong_to_customer(
    session: Session, tenant: Tenant
) -> None:
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
    api = AppointmentService(session)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=_next_monday_9am(),
            actor="t",
            service_id=setup["service_id"],
            location_id=uuid.UUID(other_location["id"]),
        )
    assert exc.value.code == "location_customer_mismatch"


def test_appointment_double_book_same_technician_conflicts(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id, duration_minutes=60)
    api = AppointmentService(session)
    starts = _next_monday_9am()
    api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
    )
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts + timedelta(minutes=30),
            actor="t",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
    assert exc.value.code == "slot_conflict"

    # Adjacent (half-open [start, end)) booking is fine.
    adjacent = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts + timedelta(minutes=60),
        actor="t",
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
    )
    assert adjacent["status"] == "SCHEDULED"


# --- Transitions ---


def test_status_machine_and_history(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = AppointmentService(session)
    appt = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=_next_monday_9am(),
        actor="t",
        service_id=setup["service_id"],
        status="TENTATIVE",
    )
    aid = uuid.UUID(appt["id"])

    with pytest.raises(CrmError) as exc:
        api.update(tenant.id, aid, status="CONFIRMED", actor="t")
    assert exc.value.code == "use_transition"

    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, aid, to_status="COMPLETED", actor="t")
    assert exc.value.code == "invalid_transition"

    api.transition(tenant.id, aid, to_status="SCHEDULED", actor="t")
    api.assign(tenant.id, aid, technician_id=setup["technician_id"], actor="t")

    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, aid, to_status="COMPLETED", actor="t")
    assert exc.value.code == "invalid_transition"  # must go through IN_PROGRESS first

    api.transition(tenant.id, aid, to_status="IN_PROGRESS", actor="t")
    done = api.transition(tenant.id, aid, to_status="COMPLETED", actor="t")
    assert done["status"] == "COMPLETED"
    assert done["completed_at"] is not None

    history = api.history(tenant.id, aid)
    to_statuses = [h["to_status"] for h in history]
    assert to_statuses == ["TENTATIVE", "SCHEDULED", "IN_PROGRESS", "COMPLETED"]


def test_requires_technician_before_in_progress(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = AppointmentService(session)
    appt = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=_next_monday_9am(),
        actor="t",
        service_id=setup["service_id"],
    )
    aid = uuid.UUID(appt["id"])
    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, aid, to_status="IN_PROGRESS", actor="t")
    assert exc.value.code == "technician_required"


def test_cancel_and_archive(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = AppointmentService(session)
    appt = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=_next_monday_9am(),
        actor="t",
        service_id=setup["service_id"],
    )
    aid = uuid.UUID(appt["id"])
    cancelled = api.cancel(tenant.id, aid, actor="t", reason="customer request")
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["cancelled_at"] is not None

    archived = api.archive(tenant.id, aid, actor="t")
    assert archived["archived_at"] is not None
    restored = api.restore(tenant.id, aid, actor="t")
    assert restored["archived_at"] is None


def test_archive_not_allowed_mid_flow(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = AppointmentService(session)
    appt = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=_next_monday_9am(),
        actor="t",
        service_id=setup["service_id"],
    )
    aid = uuid.UUID(appt["id"])
    with pytest.raises(CrmError) as exc:
        api.archive(tenant.id, aid, actor="t")
    assert exc.value.code == "archive_not_allowed"


def test_reschedule_revalidates_conflicts(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id, duration_minutes=60)
    api = AppointmentService(session)
    starts = _next_monday_9am()
    a = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
    )
    b = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts + timedelta(hours=2),
        actor="t",
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
    )
    with pytest.raises(CrmError) as exc:
        api.reschedule(
            tenant.id,
            uuid.UUID(b["id"]),
            starts_at=starts,
            actor="t",
        )
    assert exc.value.code == "slot_conflict"
    _ = a


def test_normalize_status_aliases() -> None:
    assert normalize_status("scheduled") == "SCHEDULED"
    assert normalize_status("canceled") == "CANCELLED"
    assert normalize_status("cancelled") == "CANCELLED"
    with pytest.raises(ValueError):
        normalize_status("bogus")


# --- Availability engine: skills + service area + emergency hours ---


def test_availability_engine_filters_by_required_skill(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    BusinessHoursService(session).update(
        tenant.id, actor="t", weekly_hours={"mon": [["09:00", "17:00"]]}
    )
    avail = TechnicianAvailabilityService(session)
    skill = avail.create_skill(tenant.id, key="hvac", name="HVAC", actor="t")
    avail.set_service_required_skills(
        tenant.id, setup["service_id"], [uuid.UUID(skill["id"])], actor="t"
    )

    starts = _next_monday_9am()
    engine = AvailabilityEngine(session)
    result = engine.compute(
        tenant.id,
        from_date=starts.date(),
        to_date=starts.date(),
        service_id=setup["service_id"],
        now_utc=starts - timedelta(days=1),
    )
    assert result["slots"] == []  # technician lacks the required skill

    avail.assign_technician_skill(
        tenant.id, setup["technician_id"], uuid.UUID(skill["id"]), actor="t"
    )
    result2 = engine.compute(
        tenant.id,
        from_date=starts.date(),
        to_date=starts.date(),
        service_id=setup["service_id"],
        now_utc=starts - timedelta(days=1),
    )
    assert len(result2["slots"]) > 0
    assert result2["slots"][0]["technician_id"] == str(setup["technician_id"])


def test_availability_engine_filters_by_service_area(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    BusinessHoursService(session).update(
        tenant.id, actor="t", weekly_hours={"mon": [["09:00", "17:00"]]}
    )
    avail = TechnicianAvailabilityService(session)
    area = avail.create_service_area(
        tenant.id,
        key="austin",
        name="Austin",
        match_type="CITY",
        match_value="Austin",
        actor="t",
    )

    starts = _next_monday_9am()
    engine = AvailabilityEngine(session)
    # Tenant has service areas configured but technician has no links yet —
    # must be excluded for a location that matches a defined area.
    result = engine.compute(
        tenant.id,
        from_date=starts.date(),
        to_date=starts.date(),
        location_id=setup["location_id"],
        now_utc=starts - timedelta(days=1),
    )
    assert result["slots"] == []

    avail.assign_technician_service_area(
        tenant.id, setup["technician_id"], uuid.UUID(area["id"]), actor="t"
    )
    result2 = engine.compute(
        tenant.id,
        from_date=starts.date(),
        to_date=starts.date(),
        location_id=setup["location_id"],
        now_utc=starts - timedelta(days=1),
    )
    assert len(result2["slots"]) > 0


def test_availability_engine_skips_holiday_and_subtracts_breaks(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    hours = BusinessHoursService(session)
    full_week = {
        day: [["09:00", "17:00"]]
        for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    }
    hours.update(tenant.id, actor="t", weekly_hours=full_week)

    starts = _next_monday_9am()
    hours.create_holiday(
        tenant.id, holiday_date=starts.date(), name="Closed", actor="t"
    )
    engine = AvailabilityEngine(session)
    result = engine.compute(
        tenant.id,
        from_date=starts.date(),
        to_date=starts.date(),
        technician_id=setup["technician_id"],
        now_utc=starts - timedelta(days=1),
    )
    assert result["slots"] == []  # holiday closes the whole day

    # Different day: full day free except a lunch break removes mid-day slots.
    other_day = starts + timedelta(days=1)
    avail = TechnicianAvailabilityService(session)
    avail.create_break(
        tenant.id,
        setup["technician_id"],
        day_of_week=other_day.weekday(),
        start_time="12:00",
        end_time="13:00",
        actor="t",
    )
    result2 = engine.compute(
        tenant.id,
        from_date=other_day.date(),
        to_date=other_day.date(),
        technician_id=setup["technician_id"],
        now_utc=starts - timedelta(days=2),
    )
    starts_set = {s["starts_at"] for s in result2["slots"]}
    noon_utc = datetime(
        other_day.year, other_day.month, other_day.day, 12, 0, tzinfo=UTC
    ).isoformat()
    assert noon_utc not in starts_set


# --- Technician availability CRUD validation ---


def test_schedule_period_overlap_rejected(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    avail = TechnicianAvailabilityService(session)
    avail.create_period(
        tenant.id,
        setup["technician_id"],
        day_of_week=0,
        open_time="09:00",
        close_time="12:00",
        actor="t",
    )
    with pytest.raises(CrmError) as exc:
        avail.create_period(
            tenant.id,
            setup["technician_id"],
            day_of_week=0,
            open_time="11:00",
            close_time="13:00",
            actor="t",
        )
    assert exc.value.code == "period_overlap"


def test_break_overlap_rejected(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    avail = TechnicianAvailabilityService(session)
    avail.create_break(
        tenant.id,
        setup["technician_id"],
        day_of_week=0,
        start_time="12:00",
        end_time="13:00",
        actor="t",
    )
    with pytest.raises(CrmError) as exc:
        avail.create_break(
            tenant.id,
            setup["technician_id"],
            day_of_week=0,
            start_time="12:30",
            end_time="13:30",
            actor="t",
        )
    assert exc.value.code == "break_overlap"


def test_time_off_overlap_rejected(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    avail = TechnicianAvailabilityService(session)
    starts = _next_monday_9am()
    avail.create_time_off(
        tenant.id,
        setup["technician_id"],
        starts_at=starts,
        ends_at=starts + timedelta(days=2),
        time_off_type="VACATION",
        actor="t",
    )
    with pytest.raises(CrmError) as exc:
        avail.create_time_off(
            tenant.id,
            setup["technician_id"],
            starts_at=starts + timedelta(days=1),
            ends_at=starts + timedelta(days=3),
            time_off_type="SICK",
            actor="t",
        )
    assert exc.value.code == "time_off_overlap"


def test_cross_tenant_isolation(session: Session, tenant: Tenant) -> None:
    tenant_b = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(tenant_b)
    session.flush()
    setup_a = _setup(session, tenant.id)
    setup_b = _setup(session, tenant_b.id)
    api = AppointmentService(session)
    appt = api.create(
        tenant.id,
        customer_id=setup_a["customer_id"],
        starts_at=_next_monday_9am(),
        actor="t",
        service_id=setup_a["service_id"],
    )
    aid = uuid.UUID(appt["id"])
    with pytest.raises(CrmError):
        api.get(tenant_b.id, aid)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup_b["customer_id"],
            starts_at=_next_monday_9am(),
            actor="t",
            service_id=setup_a["service_id"],
        )
    assert exc.value.code == "customer_not_found"
