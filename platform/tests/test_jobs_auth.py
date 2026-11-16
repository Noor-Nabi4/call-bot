"""Auth and jobs repository tests."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from helpers import next_open_booking_day
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.auth.repos import AuthError, AuthRepository
from callbot_platform.config import Settings
from callbot_platform.crm.repos import CustomerRepository
from callbot_platform.db.models import Job, Technician, Tenant, TenantUser
from callbot_platform.jobs.repos import JobRepository, JobsError, TechnicianRepository
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.scheduling.repos import AppointmentRepository
from callbot_platform.security.session import (
    create_session_token,
    decode_session_token,
    verify_password,
)


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Beta Co", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-for-phase5-ok32",
        internal_service_token="internal-test-token",
    )


def _fake_sms(**kwargs: object) -> str:
    return "SM_test"


def test_bootstrap_and_login(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    admin = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="Admin@Acme.Test",
        password="password123",
        name="Admin",
    )
    assert admin["role"] == "admin"
    assert admin["email"] == "admin@acme.test"
    row = session.get(TenantUser, uuid.UUID(admin["id"]))
    assert row is not None
    assert verify_password("password123", row.password_hash)

    with pytest.raises(AuthError) as exc:
        auth.bootstrap_admin(
            tenant_id=tenant.id,
            email="other@acme.test",
            password="password123",
            name="Other",
        )
    assert exc.value.code == "already_bootstrapped"

    user = auth.authenticate(
        tenant_slug=tenant.slug,
        email="admin@acme.test",
        password="password123",
    )
    assert user["id"] == admin["id"]

    with pytest.raises(AuthError):
        auth.authenticate(
            tenant_slug=tenant.slug,
            email="admin@acme.test",
            password="wrong-password",
        )


def test_update_profile_name_and_password(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    admin = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@acme.test",
        password="password123",
        name="Admin",
    )
    updated = auth.update_profile(
        tenant_id=tenant.id,
        user_id=uuid.UUID(admin["id"]),
        name="  Ada Admin  ",
        current_password="password123",
        new_password="password456",
        actor="admin@acme.test",
    )
    assert updated["name"] == "Ada Admin"
    row = session.get(TenantUser, uuid.UUID(admin["id"]))
    assert row is not None
    assert verify_password("password456", row.password_hash)

    with pytest.raises(AuthError) as bad_current:
        auth.update_profile(
            tenant_id=tenant.id,
            user_id=uuid.UUID(admin["id"]),
            current_password="wrong",
            new_password="password789",
        )
    assert bad_current.value.code == "invalid_credentials"

    with pytest.raises(AuthError) as missing_current:
        auth.update_profile(
            tenant_id=tenant.id,
            user_id=uuid.UUID(admin["id"]),
            new_password="password789",
        )
    assert missing_current.value.code == "current_password_required"


def test_update_profile_syncs_technician_display_name(
    session: Session, tenant: Tenant
) -> None:
    auth = AuthRepository(session)
    auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@acme.test",
        password="password123",
        name="Admin",
    )
    tech_user = auth.create_user(
        tenant.id,
        email="tech@acme.test",
        password="password123",
        name="Tech One",
        role="technician",
        phone="+15551112222",
    )
    updated = auth.update_profile(
        tenant_id=tenant.id,
        user_id=uuid.UUID(tech_user["id"]),
        name="Tech Two",
    )
    assert updated["name"] == "Tech Two"
    tech = session.scalar(
        select(Technician).where(Technician.user_id == uuid.UUID(tech_user["id"]))
    )
    assert tech is not None
    assert tech.display_name == "Tech Two"


def test_session_token_roundtrip(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="a@t.test",
        password="password123",
        name="A",
    )
    token = create_session_token(
        settings=session_settings,
        user_id=uuid.UUID(admin["id"]),
        tenant_id=tenant.id,
        role="admin",
        email=admin["email"],
    )
    payload = decode_session_token(token, settings=session_settings)
    assert payload["tenant_id"] == str(tenant.id)
    assert payload["sub"] == admin["id"]


def test_appointment_creates_job(session: Session, tenant: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Noor", phone="+15551230001"
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
        service_type="AC repair",
    )
    assert "job" in booked
    assert booked["job"]["status"] == "SCHEDULED"
    assert booked["job"]["appointment_id"] == booked["id"]
    job_row = session.get(Job, uuid.UUID(booked["job"]["id"]))
    assert job_row is not None
    assert job_row.tenant_id == tenant.id


def test_job_assign_dispatch_complete(session: Session, tenant: Tenant) -> None:
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="ops@t.test",
        password="password123",
        name="Ops",
    )
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Cust", phone="+15551230002"
    )
    tech = TechnicianRepository(session).create(
        tenant.id,
        email="tech@t.test",
        password="password123",
        name="Tech One",
    )
    jobs = JobRepository(session)
    job = jobs.create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="Install",
        status="scheduled",
    )
    assigned = jobs.assign(
        tenant.id, uuid.UUID(job["id"]), technician_id=uuid.UUID(tech["id"])
    )
    assert assigned["assigned_technician_id"] == tech["id"]
    dispatched = jobs.transition(tenant.id, uuid.UUID(job["id"]), status="dispatched")
    assert dispatched["status"] == "DISPATCHED"
    started = jobs.transition(tenant.id, uuid.UUID(job["id"]), status="in_progress")
    assert started["status"] == "IN_PROGRESS"
    done = jobs.transition(
        tenant.id,
        uuid.UUID(job["id"]),
        status="completed",
        completion_notes="Replaced capacitor",
        actor_user_id=uuid.UUID(tech["user_id"]),
    )
    assert done["status"] == "COMPLETED"
    assert done["completion_notes"] == "Replaced capacitor"
    assert any("Completed:" in (n["body"] or "") for n in done.get("notes") or [])


def test_invalid_transition(session: Session, tenant: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Cust", phone="+15551230003"
    )
    jobs = JobRepository(session)
    job = jobs.create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="Repair",
        status="new",
    )
    with pytest.raises(JobsError) as exc:
        jobs.transition(tenant.id, uuid.UUID(job["id"]), status="completed")
    assert exc.value.code == "invalid_transition"


def test_tenant_isolation_jobs(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Secret", phone="+15551230004"
    )
    job = JobRepository(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="Secret job",
    )
    assert JobRepository(session).get(tenant.id, uuid.UUID(job["id"])) is not None
    assert JobRepository(session).get(tenant_b.id, uuid.UUID(job["id"])) is None
