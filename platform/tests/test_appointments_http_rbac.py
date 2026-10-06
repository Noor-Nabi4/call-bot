"""HTTP-level RBAC and IDOR tests for Appointment CRM APIs (Phase 11)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.appointments.service import AppointmentService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.jobs import TenantUser
from callbot_platform.jobs.repos import TechnicianRepository
from callbot_platform.main import app
from callbot_platform.rbac.catalog import SYSTEM_ROLE_AI_AGENT, SYSTEM_ROLE_TECHNICIAN
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token

BASE = "/api/admin/crm/appointments"

ALL_APPOINTMENT_PERMS = [
    "appointments.read",
    "appointments.create",
    "appointments.update",
    "appointments.cancel",
    "appointments.transition",
    "appointments.assign",
    "appointments.availability.read",
    "appointments.business_hours.read",
    "appointments.business_hours.update",
    "appointments.technician_schedule.read",
    "appointments.technician_schedule.update",
]


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-appts-rbac-ok32chars",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
    )


def _override_db(session: Session):
    def _db() -> Generator[Session, None, None]:
        yield session

    return _db


def _client_for(
    session: Session, settings: Settings, *, token: str | None = None
) -> TestClient:
    app.dependency_overrides[db_dep] = _override_db(session)
    app.dependency_overrides[settings_dep] = lambda: settings
    get_settings.cache_clear()
    client = TestClient(app)
    if token:
        client.cookies.set(settings.session_cookie_name, token)
    return client


def _token_for(settings: Settings, user: dict, tenant: Tenant) -> str:
    return create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )


def _user_with_permissions(
    session: Session,
    tenant: Tenant,
    *,
    email: str,
    permissions: list[str],
) -> tuple[dict, dict]:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email=f"owner-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Owner",
    )
    ensure_system_roles_for_tenant(session, tenant.id)
    user = auth.create_user(
        tenant.id,
        email=email,
        password="password123",
        name="Limited",
        role="dispatcher",
        actor=owner["email"],
    )
    roles = RoleRepository(session)
    custom = roles.create_role(
        tenant.id,
        name=f"ApptLimited-{uuid.uuid4().hex[:6]}",
        description="test",
        permissions=[{"key": k, "scope": "ALL_ORGANIZATION"} for k in permissions],
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
    )
    member_roles = roles.list_member_roles(tenant.id, uuid.UUID(user["id"]))
    for r in member_roles["roles"]:
        roles.remove_role(
            tenant.id,
            member_id=uuid.UUID(user["id"]),
            role_id=uuid.UUID(r["id"]),
            actor=owner["email"],
            actor_user_id=uuid.UUID(owner["id"]),
        )
    roles.assign_role(
        tenant.id,
        member_id=uuid.UUID(user["id"]),
        role_id=uuid.UUID(custom["id"]),
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
    )
    return user, owner


def _setup_field_service(session: Session, tenant: Tenant) -> dict:
    customer = CustomerService(session).create(
        tenant.id,
        name="Cust",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    service = ServicesPricebookService(session).create_service(
        tenant.id, name="Repair", actor="t", duration_minutes=60
    )
    tech = TechnicianRepository(session).create(
        tenant.id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Field Tech",
    )
    return {
        "customer_id": customer["id"],
        "service_id": service["id"],
        "technician_id": tech["id"],
        "technician_user_id": tech["user_id"],
    }


def _next_monday_9am_iso() -> str:
    now = datetime.now(UTC)
    days_ahead = (7 - now.weekday()) % 7 or 7
    day = (now + timedelta(days=days_ahead)).date()
    return datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC).isoformat()


def test_unauthenticated_401(session: Session, session_settings: Settings) -> None:
    client = _client_for(session, session_settings)
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json={}).status_code == 401
    assert client.get("/api/admin/crm/business-hours").status_code == 401


def test_missing_permission_403(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    user, _owner = _user_with_permissions(
        session, tenant, email="noperm@t.test", permissions=["customers.read"]
    )
    client = _client_for(
        session, session_settings, token=_token_for(session_settings, user, tenant)
    )
    assert client.get(BASE).status_code == 403
    assert client.post(BASE, json={"customer_id": str(uuid.uuid4())}).status_code == 403
    assert client.get("/api/admin/crm/business-hours").status_code == 403
    assert (
        client.post("/api/admin/crm/appointments/availability", json={}).status_code
        == 403
    )


def test_authorized_full_lifecycle(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    user, _owner = _user_with_permissions(
        session, tenant, email="full@t.test", permissions=ALL_APPOINTMENT_PERMS
    )
    setup = _setup_field_service(session, tenant)
    client = _client_for(
        session, session_settings, token=_token_for(session_settings, user, tenant)
    )
    starts_at = _next_monday_9am_iso()

    created = client.post(
        BASE,
        json={
            "customer_id": setup["customer_id"],
            "service_id": setup["service_id"],
            "starts_at": starts_at,
            "status": "TENTATIVE",
        },
    )
    assert created.status_code == 201, created.text
    appt_id = created.json()["appointment"]["id"]
    assert created.json()["appointment"]["appointment_number"].startswith("APT-")

    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{appt_id}").status_code == 200
    assert client.get(f"{BASE}/{appt_id}/history").status_code == 200

    patch = client.patch(f"{BASE}/{appt_id}", json={"notes": "Bring parts"})
    assert patch.status_code == 200
    assert patch.json()["appointment"]["notes"] == "Bring parts"

    assign = client.post(
        f"{BASE}/{appt_id}/assign", json={"technician_id": setup["technician_id"]}
    )
    assert assign.status_code == 200
    assert (
        assign.json()["appointment"]["assigned_technician_id"] == setup["technician_id"]
    )

    scheduled = client.post(
        f"{BASE}/{appt_id}/transition", json={"to_status": "SCHEDULED"}
    )
    assert scheduled.status_code == 200, scheduled.text

    in_progress = client.post(
        f"{BASE}/{appt_id}/transition", json={"to_status": "IN_PROGRESS"}
    )
    assert in_progress.status_code == 200

    completed = client.post(
        f"{BASE}/{appt_id}/transition", json={"to_status": "COMPLETED"}
    )
    assert completed.status_code == 200
    assert completed.json()["appointment"]["status"] == "COMPLETED"

    archived = client.delete(f"{BASE}/{appt_id}")
    assert archived.status_code == 200
    restored = client.post(f"{BASE}/{appt_id}/restore")
    assert restored.status_code == 200

    # Business hours + holidays.
    hours = client.patch(
        "/api/admin/crm/business-hours",
        json={"slot_minutes": 30, "weekly_hours": {"mon": [["09:00", "17:00"]]}},
    )
    assert hours.status_code == 200, hours.text
    assert hours.json()["business_hours"]["slot_minutes"] == 30
    assert client.get("/api/admin/crm/business-hours").status_code == 200

    holiday = client.post(
        "/api/admin/crm/business-hours/holidays",
        json={"holiday_date": "2031-01-01", "name": "New Year"},
    )
    assert holiday.status_code == 201, holiday.text
    holiday_id = holiday.json()["holiday"]["id"]
    assert client.get("/api/admin/crm/business-hours/holidays").status_code == 200
    assert (
        client.delete(
            f"/api/admin/crm/business-hours/holidays/{holiday_id}"
        ).status_code
        == 200
    )

    # Technician schedule periods / breaks / time off.
    tech_id = setup["technician_id"]
    period = client.post(
        f"/api/admin/crm/technicians/{tech_id}/schedule-periods",
        json={"day_of_week": 0, "open_time": "08:00", "close_time": "16:00"},
    )
    assert period.status_code == 201, period.text
    period_id = period.json()["period"]["id"]
    assert (
        client.get(f"/api/admin/crm/technicians/{tech_id}/schedule-periods").status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/admin/crm/technicians/{tech_id}/schedule-periods/{period_id}"
        ).status_code
        == 200
    )

    brk = client.post(
        f"/api/admin/crm/technicians/{tech_id}/breaks",
        json={"day_of_week": 0, "start_time": "12:00", "end_time": "13:00"},
    )
    assert brk.status_code == 201
    break_id = brk.json()["break"]["id"]
    assert (
        client.delete(
            f"/api/admin/crm/technicians/{tech_id}/breaks/{break_id}"
        ).status_code
        == 200
    )

    # Skills + service areas.
    skill = client.post("/api/admin/crm/skills", json={"key": "hvac", "name": "HVAC"})
    assert skill.status_code == 201
    skill_id = skill.json()["skill"]["id"]
    assert (
        client.post(
            f"/api/admin/crm/technicians/{tech_id}/skills/{skill_id}"
        ).status_code
        == 201
    )
    assert client.get(f"/api/admin/crm/technicians/{tech_id}/skills").status_code == 200
    assert (
        client.delete(
            f"/api/admin/crm/technicians/{tech_id}/skills/{skill_id}"
        ).status_code
        == 200
    )

    area = client.post(
        "/api/admin/crm/service-areas",
        json={
            "key": "austin",
            "name": "Austin",
            "match_type": "CITY",
            "match_value": "Austin",
        },
    )
    assert area.status_code == 201
    area_id = area.json()["service_area"]["id"]
    assert (
        client.post(
            f"/api/admin/crm/technicians/{tech_id}/service-areas/{area_id}"
        ).status_code
        == 201
    )

    # Availability query.
    avail = client.post(
        "/api/admin/crm/appointments/availability",
        json={
            "from_date": starts_at[:10],
            "to_date": starts_at[:10],
            "technician_id": tech_id,
        },
    )
    assert avail.status_code == 200, avail.text
    assert "slots" in avail.json()


def test_ai_cannot_assign_or_transition_but_can_read_create_availability(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email=f"owner-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Owner",
    )
    ensure_system_roles_for_tenant(session, tenant.id)
    roles = RoleRepository(session)
    role_map = {r["name"]: r for r in roles.list_roles(tenant.id)}
    ai_role = role_map[SYSTEM_ROLE_AI_AGENT]
    ai_user = auth.create_user(
        tenant.id,
        email=f"ai-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="AI",
        role="admin",
        actor=owner["email"],
    )
    member_roles = roles.list_member_roles(tenant.id, uuid.UUID(ai_user["id"]))
    for r in member_roles["roles"]:
        roles.remove_role(
            tenant.id,
            member_id=uuid.UUID(ai_user["id"]),
            role_id=uuid.UUID(r["id"]),
            actor=owner["email"],
            actor_user_id=uuid.UUID(owner["id"]),
        )
    roles.assign_role(
        tenant.id,
        member_id=uuid.UUID(ai_user["id"]),
        role_id=uuid.UUID(ai_role["id"]),
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
    )
    setup = _setup_field_service(session, tenant)
    client = _client_for(
        session, session_settings, token=_token_for(session_settings, ai_user, tenant)
    )
    starts_at = _next_monday_9am_iso()

    created = client.post(
        BASE,
        json={
            "customer_id": setup["customer_id"],
            "service_id": setup["service_id"],
            "starts_at": starts_at,
        },
    )
    assert created.status_code == 201, created.text
    appt_id = created.json()["appointment"]["id"]

    assert client.get(f"{BASE}/{appt_id}").status_code == 200

    avail = client.post(
        "/api/admin/crm/appointments/availability",
        json={"from_date": starts_at[:10], "to_date": starts_at[:10]},
    )
    assert avail.status_code == 200, avail.text

    assert (
        client.post(
            f"{BASE}/{appt_id}/assign", json={"technician_id": setup["technician_id"]}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{BASE}/{appt_id}/transition", json={"to_status": "SCHEDULED"}
        ).status_code
        == 403
    )
    assert client.get("/api/admin/crm/business-hours").status_code == 403
    assert (
        client.get(
            f"/api/admin/crm/technicians/{setup['technician_id']}/schedule-periods"
        ).status_code
        == 403
    )

    # AI Agent retains the pre-existing cancel permission.
    cancel = client.post(
        f"{BASE}/{appt_id}/cancel", json={"reason": "no longer needed"}
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["appointment"]["status"] == "CANCELLED"


def test_technician_assigned_scope(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    dispatcher, owner = _user_with_permissions(
        session, tenant, email="dispatch@t.test", permissions=ALL_APPOINTMENT_PERMS
    )
    setup = _setup_field_service(session, tenant)
    roles = RoleRepository(session)
    role_map = {r["name"]: r for r in roles.list_roles(tenant.id)}
    tech_role = role_map[SYSTEM_ROLE_TECHNICIAN]

    dispatch_client = _client_for(
        session,
        session_settings,
        token=_token_for(session_settings, dispatcher, tenant),
    )
    starts_at = _next_monday_9am_iso()
    created = dispatch_client.post(
        BASE,
        json={
            "customer_id": setup["customer_id"],
            "service_id": setup["service_id"],
            "starts_at": starts_at,
        },
    )
    assert created.status_code == 201
    appt_id = created.json()["appointment"]["id"]
    assign = dispatch_client.post(
        f"{BASE}/{appt_id}/assign", json={"technician_id": setup["technician_id"]}
    )
    assert assign.status_code == 200

    tech_user = session.scalar(
        select(TenantUser).where(
            TenantUser.id == uuid.UUID(setup["technician_user_id"])
        )
    )
    assert tech_user is not None
    member_roles = roles.list_member_roles(tenant.id, tech_user.id)
    for r in member_roles["roles"]:
        roles.remove_role(
            tenant.id,
            member_id=tech_user.id,
            role_id=uuid.UUID(r["id"]),
            actor=owner["email"],
            actor_user_id=uuid.UUID(owner["id"]),
        )
    roles.assign_role(
        tenant.id,
        member_id=tech_user.id,
        role_id=uuid.UUID(tech_role["id"]),
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
    )
    tech_token = create_session_token(
        settings=session_settings,
        user_id=tech_user.id,
        tenant_id=tenant.id,
        role="technician",
        email=tech_user.email,
    )
    tech_client = _client_for(session, session_settings, token=tech_token)

    # Technician can read their own assigned appointment via ASSIGNED scope.
    assert tech_client.get(f"{BASE}/{appt_id}").status_code == 200
    assert tech_client.get(BASE).status_code == 200

    # Technician cannot (re)assign or transition appointments.
    assert (
        tech_client.post(
            f"{BASE}/{appt_id}/assign", json={"technician_id": None}
        ).status_code
        == 403
    )
    assert (
        tech_client.post(
            f"{BASE}/{appt_id}/transition", json={"to_status": "SCHEDULED"}
        ).status_code
        == 403
    )


def test_idor_cross_tenant(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    tenant_b = Tenant(name="B", slug=f"b-{uuid.uuid4().hex[:8]}")
    session.add(tenant_b)
    session.flush()

    user_a, _owner_a = _user_with_permissions(
        session, tenant, email="a@t.test", permissions=ALL_APPOINTMENT_PERMS
    )
    user_b, _owner_b = _user_with_permissions(
        session, tenant_b, email="b@t.test", permissions=ALL_APPOINTMENT_PERMS
    )
    setup_a = _setup_field_service(session, tenant)
    setup_b = _setup_field_service(session, tenant_b)

    appt_a = AppointmentService(session).create(
        tenant.id,
        customer_id=uuid.UUID(setup_a["customer_id"]),
        starts_at=datetime.fromisoformat(_next_monday_9am_iso()),
        actor="t",
        service_id=uuid.UUID(setup_a["service_id"]),
    )
    client_b = _client_for(
        session, session_settings, token=_token_for(session_settings, user_b, tenant_b)
    )
    aid = appt_a["id"]
    assert client_b.get(f"{BASE}/{aid}").status_code == 404
    assert client_b.patch(f"{BASE}/{aid}", json={"notes": "x"}).status_code == 404
    assert client_b.delete(f"{BASE}/{aid}").status_code == 404
    assert client_b.post(f"{BASE}/{aid}/restore").status_code == 404
    assert (
        client_b.post(
            f"{BASE}/{aid}/transition", json={"to_status": "SCHEDULED"}
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            f"{BASE}/{aid}/assign",
            json={"technician_id": setup_b["technician_id"]},
        ).status_code
        == 404
    )
    assert client_b.get(f"{BASE}/{aid}/history").status_code == 404

    # Cross-tenant customer/service on create.
    client_a = _client_for(
        session, session_settings, token=_token_for(session_settings, user_a, tenant)
    )
    bad = client_a.post(
        BASE,
        json={
            "customer_id": setup_b["customer_id"],
            "service_id": setup_a["service_id"],
            "starts_at": _next_monday_9am_iso(),
        },
    )
    assert bad.status_code == 404
