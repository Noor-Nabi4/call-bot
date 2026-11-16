"""HTTP RBAC / IDOR for Phase 12 Dispatch APIs."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.jobs import JobService
from callbot_platform.db.models import Tenant
from callbot_platform.jobs.repos import TechnicianRepository
from callbot_platform.main import app
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token

BASE = "/api/admin/crm/dispatch"


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-dispatch-rbac-ok32c",
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


def _admin_token(session: Session, settings: Settings, tenant: Tenant) -> str:
    ensure_system_roles_for_tenant(session, tenant.id)
    user = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email=f"owner-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Owner",
    )
    return create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )


def test_board_requires_auth(session: Session, session_settings: Settings) -> None:
    client = _client_for(session, session_settings)
    assert client.get(f"{BASE}/board").status_code in {401, 403}


def test_board_and_assign_happy_path(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    token = _admin_token(session, session_settings, tenant)
    customer = CustomerService(session).create(
        tenant.id, name="C", phone="+15551234567", actor="t"
    )
    tech = TechnicianRepository(session).create(
        tenant.id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Tech",
    )
    job = JobService(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        actor="t",
        service_type="Fix",
        scheduled_starts_at=datetime.now(UTC) + timedelta(hours=2),
    )
    client = _client_for(session, session_settings, token=token)

    board = client.get(f"{BASE}/board")
    assert board.status_code == 200, board.text
    assert "technicians" in board.json()

    assign = client.post(
        f"{BASE}/jobs/{job['id']}/assign",
        json={"technician_id": tech["id"]},
    )
    assert assign.status_code == 200, assign.text
    assert assign.json()["job"]["assigned_technician_id"] == tech["id"]

    hist = client.get(f"{BASE}/jobs/{job['id']}/assignment-history")
    assert hist.status_code == 200
    assert len(hist.json()["history"]) >= 1


def test_cross_tenant_idor(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    token = _admin_token(session, session_settings, tenant)
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    ensure_system_roles_for_tenant(session, other.id)
    tech_b = TechnicianRepository(session).create(
        other.id,
        email=f"techb-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Other",
    )
    cust_b = CustomerService(session).create(
        other.id, name="B", phone="+15557654321", actor="t"
    )
    job_b = JobService(session).create(
        other.id,
        customer_id=uuid.UUID(cust_b["id"]),
        actor="t",
        service_type="X",
    )
    client = _client_for(session, session_settings, token=token)
    assert client.get(f"{BASE}/technicians/{tech_b['id']}/status").status_code in {
        403,
        404,
    }
    assert client.post(
        f"{BASE}/jobs/{job_b['id']}/assign",
        json={"technician_id": tech_b["id"]},
    ).status_code in {403, 404}


def test_legacy_and_crm_assign_http_parity(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    """Legacy /api/jobs/{id}/assign and CRM dispatch assign share side effects."""
    from sqlalchemy import select

    from callbot_platform.db.models.dispatch import DispatchEvent, JobAssignmentHistory
    from callbot_platform.rbac.catalog import SYSTEM_ROLE_AI_AGENT
    from callbot_platform.rbac.repos import RoleRepository
    from callbot_platform.rbac.service import AuthorizationService

    ensure_system_roles_for_tenant(session, tenant.id)
    owner = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email=f"owner-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Owner",
    )
    token = create_session_token(
        settings=session_settings,
        user_id=uuid.UUID(owner["id"]),
        tenant_id=tenant.id,
        role=owner["role"],
        email=owner["email"],
    )
    customer = CustomerService(session).create(
        tenant.id, name="C", phone="+15551234567", actor="t"
    )
    tech = TechnicianRepository(session).create(
        tenant.id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Tech",
    )
    tech_b = TechnicianRepository(session).create(
        tenant.id,
        email=f"techb-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Tech B",
    )
    job_legacy = JobService(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        actor="t",
        service_type="LegacyPath",
    )
    job_crm = JobService(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        actor="t",
        service_type="CrmPath",
    )
    client = _client_for(session, session_settings, token=token)

    legacy = client.post(
        f"/api/jobs/{job_legacy['id']}/assign",
        json={"technician_id": tech["id"]},
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["job"]["assigned_technician_id"] == tech["id"]

    crm = client.post(
        f"{BASE}/jobs/{job_crm['id']}/assign",
        json={"technician_id": tech_b["id"]},
    )
    assert crm.status_code == 200, crm.text
    assert crm.json()["job"]["assigned_technician_id"] == tech_b["id"]

    for jid in (job_legacy["id"], job_crm["id"]):
        hist = list(
            session.scalars(
                select(JobAssignmentHistory).where(
                    JobAssignmentHistory.tenant_id == tenant.id,
                    JobAssignmentHistory.job_id == uuid.UUID(jid),
                )
            ).all()
        )
        assert len(hist) >= 1
        events = list(
            session.scalars(
                select(DispatchEvent).where(
                    DispatchEvent.tenant_id == tenant.id,
                    DispatchEvent.event_type.in_(("JOB_ASSIGNED", "JOB_REASSIGNED")),
                )
            ).all()
        )
        assert len(events) >= 2

    # AI Agent may read dispatch / technicians but cannot assign or update status.
    roles = RoleRepository(session)
    role_map = {r["name"]: r for r in roles.list_roles(tenant.id)}
    ai_role = role_map[SYSTEM_ROLE_AI_AGENT]
    ai_user = AuthRepository(session).create_user(
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
    authz = AuthorizationService(session)
    assert authz.has_permission(tenant.id, uuid.UUID(ai_user["id"]), "dispatch.read")
    assert authz.has_permission(tenant.id, uuid.UUID(ai_user["id"]), "technicians.read")
    assert not authz.has_permission(tenant.id, uuid.UUID(ai_user["id"]), "jobs.assign")
    assert not authz.has_permission(
        tenant.id, uuid.UUID(ai_user["id"]), "dispatch.status.update"
    )
    ai_token = create_session_token(
        settings=session_settings,
        user_id=uuid.UUID(ai_user["id"]),
        tenant_id=tenant.id,
        role=ai_user["role"],
        email=ai_user["email"],
    )
    ai_client = _client_for(session, session_settings, token=ai_token)
    assert ai_client.get(f"{BASE}/board").status_code == 200
    assert (
        ai_client.post(
            f"{BASE}/jobs/{job_crm['id']}/assign",
            json={"technician_id": tech["id"]},
        ).status_code
        == 403
    )
