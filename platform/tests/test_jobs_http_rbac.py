"""HTTP-level RBAC and IDOR tests for Job CRM APIs (Phase 10)."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.jobs import JobService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.jobs import TenantUser
from callbot_platform.jobs.repos import TechnicianRepository
from callbot_platform.main import app
from callbot_platform.rbac.catalog import SYSTEM_ROLE_AI_AGENT, SYSTEM_ROLE_TECHNICIAN
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token

BASE = "/api/admin/crm/jobs"

ALL_JOB_PERMS = [
    "jobs.read",
    "jobs.create",
    "jobs.update",
    "jobs.delete",
    "jobs.assign",
    "jobs.transition",
    "jobs.notes.read",
    "jobs.notes.create",
    "jobs.notes.update",
    "jobs.notes.delete",
    "jobs.attachments.read",
    "jobs.attachments.create",
    "jobs.attachments.delete",
]


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-jobs-rbac-ok32chars",
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
) -> dict:
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
        name=f"JobLimited-{uuid.uuid4().hex[:6]}",
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
        tenant.id, name="Repair", actor="t"
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


def test_unauthenticated_401(session: Session, session_settings: Settings) -> None:
    client = _client_for(session, session_settings)
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json={}).status_code == 401


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


def test_authorized_crud_transition_assign_notes_attachments(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    user, _owner = _user_with_permissions(
        session, tenant, email="full@t.test", permissions=ALL_JOB_PERMS
    )
    setup = _setup_field_service(session, tenant)
    client = _client_for(
        session, session_settings, token=_token_for(session_settings, user, tenant)
    )
    created = client.post(
        BASE,
        json={
            "customer_id": setup["customer_id"],
            "service_id": setup["service_id"],
            "status": "SCHEDULED",
        },
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["job"]["id"]

    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{job_id}").status_code == 200
    assert client.get(f"{BASE}/{job_id}/history").status_code == 200

    patch = client.patch(f"{BASE}/{job_id}", json={"description": "Fix AC"})
    assert patch.status_code == 200
    assert patch.json()["job"]["description"] == "Fix AC"

    assign = client.post(
        f"{BASE}/{job_id}/assign", json={"technician_id": setup["technician_id"]}
    )
    assert assign.status_code == 200
    assert assign.json()["job"]["assigned_technician_id"] == setup["technician_id"]

    dispatched = client.post(
        f"{BASE}/{job_id}/transition", json={"to_status": "DISPATCHED"}
    )
    assert dispatched.status_code == 200, dispatched.text

    in_progress = client.post(
        f"{BASE}/{job_id}/transition", json={"to_status": "IN_PROGRESS"}
    )
    assert in_progress.status_code == 200

    missing_notes = client.post(
        f"{BASE}/{job_id}/transition", json={"to_status": "COMPLETED"}
    )
    assert missing_notes.status_code == 400

    completed = client.post(
        f"{BASE}/{job_id}/transition",
        json={"to_status": "COMPLETED", "completion_notes": "Fixed it"},
    )
    assert completed.status_code == 200
    assert completed.json()["job"]["status"] == "COMPLETED"

    note = client.post(f"{BASE}/{job_id}/notes", json={"body": "Customer satisfied"})
    assert note.status_code == 201
    note_id = note.json()["note"]["id"]
    assert client.get(f"{BASE}/{job_id}/notes").status_code == 200
    upd_note = client.patch(
        f"{BASE}/{job_id}/notes/{note_id}", json={"body": "Updated note"}
    )
    assert upd_note.status_code == 200
    assert client.delete(f"{BASE}/{job_id}/notes/{note_id}").status_code == 200

    upload = client.post(
        f"{BASE}/{job_id}/attachments",
        files={"file": ("photo.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
    )
    assert upload.status_code == 201, upload.text
    attachment_id = upload.json()["attachment"]["id"]
    assert client.get(f"{BASE}/{job_id}/attachments").status_code == 200
    assert (
        client.delete(f"{BASE}/{job_id}/attachments/{attachment_id}").status_code == 200
    )

    archived = client.delete(f"{BASE}/{job_id}")
    assert archived.status_code == 200
    restored = client.post(f"{BASE}/{job_id}/restore")
    assert restored.status_code == 200


def test_ai_cannot_delete_assign_or_transition(
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
    created = client.post(
        BASE,
        json={"customer_id": setup["customer_id"], "service_id": setup["service_id"]},
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["job"]["id"]

    assert (
        client.post(
            f"{BASE}/{job_id}/assign", json={"technician_id": setup["technician_id"]}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{BASE}/{job_id}/transition", json={"to_status": "SCHEDULED"}
        ).status_code
        == 403
    )
    assert client.delete(f"{BASE}/{job_id}").status_code == 403
    # Notes read/create allowed, update/delete not.
    note = client.post(f"{BASE}/{job_id}/notes", json={"body": "AI note"})
    assert note.status_code == 201
    note_id = note.json()["note"]["id"]
    assert client.get(f"{BASE}/{job_id}/notes").status_code == 200
    assert (
        client.patch(
            f"{BASE}/{job_id}/notes/{note_id}", json={"body": "edited"}
        ).status_code
        == 403
    )
    assert client.delete(f"{BASE}/{job_id}/notes/{note_id}").status_code == 403
    # Attachments not granted to AI Agent at all.
    assert client.get(f"{BASE}/{job_id}/attachments").status_code == 403


def test_technician_assigned_scope(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    # Dispatcher-equivalent user (bootstraps the tenant's first/owner user).
    dispatcher, owner = _user_with_permissions(
        session, tenant, email="dispatch@t.test", permissions=ALL_JOB_PERMS
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
    created = dispatch_client.post(
        BASE,
        json={
            "customer_id": setup["customer_id"],
            "service_id": setup["service_id"],
            "status": "SCHEDULED",
        },
    )
    assert created.status_code == 201
    job_id = created.json()["job"]["id"]
    assign = dispatch_client.post(
        f"{BASE}/{job_id}/assign", json={"technician_id": setup["technician_id"]}
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

    # Technician can read/update their assigned job via ASSIGNED scope.
    assert tech_client.get(f"{BASE}/{job_id}").status_code == 200
    assert (
        tech_client.patch(
            f"{BASE}/{job_id}", json={"description": "On my way"}
        ).status_code
        == 200
    )
    note = tech_client.post(f"{BASE}/{job_id}/notes", json={"body": "Arrived"})
    assert note.status_code == 201

    # Technician cannot assign or delete jobs.
    assert (
        tech_client.post(
            f"{BASE}/{job_id}/assign", json={"technician_id": None}
        ).status_code
        == 403
    )
    assert tech_client.delete(f"{BASE}/{job_id}").status_code == 403


def test_idor_cross_tenant(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    tenant_b = Tenant(name="B", slug=f"b-{uuid.uuid4().hex[:8]}")
    session.add(tenant_b)
    session.flush()

    # Bootstrap owners/users before creating technicians (which also create
    # tenant_users rows and would break AuthRepository.bootstrap_admin's
    # "first user" precondition).
    user_a, _owner_a = _user_with_permissions(
        session, tenant, email="a@t.test", permissions=ALL_JOB_PERMS
    )
    user_b, _owner_b = _user_with_permissions(
        session, tenant_b, email="b@t.test", permissions=ALL_JOB_PERMS
    )
    setup_a = _setup_field_service(session, tenant)
    setup_b = _setup_field_service(session, tenant_b)

    job_a = JobService(session).create(
        tenant.id,
        customer_id=uuid.UUID(setup_a["customer_id"]),
        actor="t",
        service_id=uuid.UUID(setup_a["service_id"]),
    )
    client_b = _client_for(
        session, session_settings, token=_token_for(session_settings, user_b, tenant_b)
    )
    jid = job_a["id"]
    assert client_b.get(f"{BASE}/{jid}").status_code == 404
    assert client_b.patch(f"{BASE}/{jid}", json={"description": "x"}).status_code == 404
    assert client_b.delete(f"{BASE}/{jid}").status_code == 404
    assert client_b.post(f"{BASE}/{jid}/restore").status_code == 404
    assert (
        client_b.post(
            f"{BASE}/{jid}/transition", json={"to_status": "SCHEDULED"}
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            f"{BASE}/{jid}/assign", json={"technician_id": setup_b["technician_id"]}
        ).status_code
        == 404
    )
    assert client_b.get(f"{BASE}/{jid}/history").status_code == 404
    assert client_b.get(f"{BASE}/{jid}/notes").status_code == 404
    assert client_b.get(f"{BASE}/{jid}/attachments").status_code == 404

    # Cross-tenant customer/service on create.
    client_a = _client_for(
        session, session_settings, token=_token_for(session_settings, user_a, tenant)
    )
    bad = client_a.post(
        BASE,
        json={
            "customer_id": setup_b["customer_id"],
            "service_id": setup_a["service_id"],
        },
    )
    assert bad.status_code == 404
