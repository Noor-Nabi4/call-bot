"""Scheduling availability and booking tests."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.repos import CustomerRepository
from callbot_platform.db.models import NotificationOutbox, Tenant
from callbot_platform.scheduling.availability import (
    filter_free_slots,
    generate_candidate_slots,
    ranges_overlap,
)
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.scheduling.repos import AppointmentRepository, SchedulingError
from helpers import next_open_booking_day


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(
        name="Beta Plumbing",
        slug=f"beta-{uuid.uuid4().hex[:8]}",
        timezone="America/New_York",
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture()
def pacific_tenant(session: Session) -> Tenant:
    row = Tenant(
        name="Pacific HVAC",
        slug=f"pac-{uuid.uuid4().hex[:8]}",
        timezone="America/Los_Angeles",
    )
    session.add(row)
    session.flush()
    return row


def _fake_sms(**kwargs: object) -> str:
    return "SM_test_sid"


def test_ranges_overlap() -> None:
    a0 = datetime(2026, 7, 20, 15, 0, tzinfo=UTC)
    a1 = datetime(2026, 7, 20, 16, 0, tzinfo=UTC)
    b0 = datetime(2026, 7, 20, 15, 30, tzinfo=UTC)
    b1 = datetime(2026, 7, 20, 16, 30, tzinfo=UTC)
    assert ranges_overlap(a0, a1, b0, b1)
    assert not ranges_overlap(a0, a1, a1, b1)


def test_generate_slots_skips_past_and_respects_tz() -> None:
    # Monday 2026-07-20 in LA; generate from a fixed "now" Sunday evening UTC.
    now = datetime(2026, 7, 20, 14, 0, tzinfo=UTC)  # 07:00 LA
    weekly = {
        "mon": [["09:00", "12:00"]],
        "tue": [],
        "wed": [],
        "thu": [],
        "fri": [],
        "sat": [],
        "sun": [],
    }
    slots = generate_candidate_slots(
        timezone_name="America/Los_Angeles",
        weekly_hours=weekly,
        slot_minutes=60,
        from_date=date(2026, 7, 20),
        to_date=date(2026, 7, 20),
        now_utc=now,
    )
    assert len(slots) == 3  # 09, 10, 11 local
    assert slots[0].local_start.startswith("2026-07-20T09:00:00")
    # 09:00 LA = 16:00 UTC in July (PDT)
    assert slots[0].starts_at == datetime(2026, 7, 20, 16, 0, tzinfo=UTC)


def test_filter_free_slots_subtracts_booked() -> None:
    candidates = generate_candidate_slots(
        timezone_name="UTC",
        weekly_hours={
            "mon": [["09:00", "12:00"]],
            "tue": [],
            "wed": [],
            "thu": [],
            "fri": [],
            "sat": [],
            "sun": [],
        },
        slot_minutes=60,
        from_date=date(2026, 7, 20),
        to_date=date(2026, 7, 20),
        now_utc=datetime(2026, 7, 19, tzinfo=UTC),
    )
    booked = [
        (
            datetime(2026, 7, 20, 10, 0, tzinfo=UTC),
            datetime(2026, 7, 20, 11, 0, tzinfo=UTC),
        )
    ]
    free = filter_free_slots(candidates, booked)
    starts = {s.starts_at for s in free}
    assert datetime(2026, 7, 20, 10, 0, tzinfo=UTC) not in starts
    assert datetime(2026, 7, 20, 9, 0, tzinfo=UTC) in starts


def test_book_and_double_book_rejected(session: Session, tenant: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Noor", phone="+15551110001"
    )
    repo = AppointmentRepository(
        session,
        notification_service=NotificationService(session, sms_sender=_fake_sms),
    )
    # Find a future Monday slot in UTC tenant default hours.
    day = next_open_booking_day()
    slots = repo.list_available_slots(
        tenant.id,
        from_date=day,
        to_date=day,
    )
    assert slots["slots"], "expected weekday slots"
    start = datetime.fromisoformat(slots["slots"][0]["starts_at"])
    first = repo.book(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        starts_at=start,
        service_type="AC repair",
        idempotency_key="book-1",
    )
    assert first["confirmation_code"].startswith("APT-")
    assert first["status"] == "scheduled"

    with pytest.raises(SchedulingError) as exc:
        repo.book(
            tenant.id,
            customer_id=uuid.UUID(customer["id"]),
            starts_at=start,
            service_type="Duplicate",
            idempotency_key="book-2",
        )
    assert exc.value.code == "slot_unavailable"


def test_cancel_frees_slot(session: Session, tenant: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Noor", phone="+15551110002"
    )
    repo = AppointmentRepository(
        session,
        notification_service=NotificationService(session, sms_sender=_fake_sms),
    )
    day = next_open_booking_day()
    slots = repo.list_available_slots(tenant.id, from_date=day, to_date=day)
    start = datetime.fromisoformat(slots["slots"][0]["starts_at"])
    booked = repo.book(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        starts_at=start,
        service_type="Heat",
    )
    repo.cancel(tenant.id, uuid.UUID(booked["id"]))
    again = repo.list_available_slots(tenant.id, from_date=day, to_date=day)
    assert any(s["starts_at"] == booked["starts_at"] for s in again["slots"])


def test_idempotent_book(session: Session, tenant: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Noor", phone="+15551110003"
    )
    repo = AppointmentRepository(
        session,
        notification_service=NotificationService(session, sms_sender=_fake_sms),
    )
    day = next_open_booking_day()
    slots = repo.list_available_slots(tenant.id, from_date=day, to_date=day)
    start = datetime.fromisoformat(slots["slots"][0]["starts_at"])
    a = repo.book(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        starts_at=start,
        service_type="AC",
        idempotency_key="same-key",
    )
    b = repo.book(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        starts_at=start + timedelta(hours=1),
        service_type="AC OTHER",
        idempotency_key="same-key",
    )
    assert a["id"] == b["id"]
    assert a["service_type"] == b["service_type"] == "AC"


def test_tenant_isolation_get(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Secret", phone="+15551110004"
    )
    repo = AppointmentRepository(
        session,
        notification_service=NotificationService(session, sms_sender=_fake_sms),
    )
    day = next_open_booking_day()
    slots = repo.list_available_slots(tenant.id, from_date=day, to_date=day)
    start = datetime.fromisoformat(slots["slots"][0]["starts_at"])
    appt = repo.book(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        starts_at=start,
        service_type="AC",
    )
    assert repo.get(tenant.id, uuid.UUID(appt["id"])) is not None
    assert repo.get(tenant_b.id, uuid.UUID(appt["id"])) is None


def test_reschedule(session: Session, tenant: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Noor", phone="+15551110005"
    )
    repo = AppointmentRepository(
        session,
        notification_service=NotificationService(session, sms_sender=_fake_sms),
    )
    day = next_open_booking_day()
    slots = repo.list_available_slots(tenant.id, from_date=day, to_date=day)
    assert len(slots["slots"]) >= 2
    start = datetime.fromisoformat(slots["slots"][0]["starts_at"])
    new_start = datetime.fromisoformat(slots["slots"][1]["starts_at"])
    appt = repo.book(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        starts_at=start,
        service_type="AC",
    )
    moved = repo.reschedule(tenant.id, uuid.UUID(appt["id"]), starts_at=new_start)
    assert moved["starts_at"] == slots["slots"][1]["starts_at"]
    assert moved["confirmation_code"] == appt["confirmation_code"]


def test_sms_outbox_and_email_pending(session: Session, pacific_tenant: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        pacific_tenant.id,
        name="Noor",
        phone="+15551110006",
        email="noor@example.com",
    )
    repo = AppointmentRepository(
        session,
        notification_service=NotificationService(session, sms_sender=_fake_sms),
    )
    day = next_open_booking_day()
    slots = repo.list_available_slots(
        pacific_tenant.id,
        from_date=day,
        to_date=day,
    )
    start = datetime.fromisoformat(slots["slots"][0]["starts_at"])
    appt = repo.book(
        pacific_tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        starts_at=start,
        service_type="AC",
    )
    assert any(
        n["channel"] == "sms" and n["status"] == "pending"
        for n in appt["notifications"]
    )
    assert any(
        n["channel"] == "email" and n["status"] == "pending"
        for n in appt["notifications"]
    )
    from sqlalchemy import select

    rows = session.scalars(
        select(NotificationOutbox).where(
            NotificationOutbox.appointment_id == uuid.UUID(appt["id"])
        )
    ).all()
    assert len(rows) == 2
