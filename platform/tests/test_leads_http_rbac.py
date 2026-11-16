"""HTTP-level RBAC and IDOR tests for Lead CRM APIs (Phase 8 hardening)."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.leads import LeadService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.crm.services import ServicesPricebookService
from callbot_platform.db.models import Tenant, TenantUser
from callbot_platform.main import app
from callbot_platform.organization.membership import MEMBERSHIP_ACTIVE
from callbot_platform.rbac.catalog import SYSTEM_ROLE_AI_AGENT
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token

BASE = "/api/admin/crm/leads"

ALL_LEAD_PERMS = [
    "leads.read",
    "leads.create",
    "leads.update",
    "leads.delete",
    "leads.assign",
    "leads.transition",
    "leads.convert",
    "leads.notes.read",
    "leads.notes.create",
    "leads.notes.update",
    "leads.notes.delete",
]


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-leads-rbac-ok32chars",
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
        name=f"LeadLimited-{uuid.uuid4().hex[:6]}",
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
    return user


def _ai_user(session: Session, tenant: Tenant) -> dict:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email=f"owner-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Owner",
    )
    ensure_system_roles_for_tenant(session, tenant.id)
    ai_user = auth.create_user(
        tenant.id,
        email=f"ai-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="AI",
        role="dispatcher",
        actor=owner["email"],
    )
    roles = RoleRepository(session)
    role_map = {r["name"]: r for r in roles.list_roles(tenant.id)}
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
        role_id=uuid.UUID(role_map[SYSTEM_ROLE_AI_AGENT]["id"]),
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
    )
    return ai_user


def _seed_lead(session: Session, tenant_id: uuid.UUID, **kwargs) -> dict:
    return LeadService(session).create(
        tenant_id, title=kwargs.pop("title", "Seed Lead"), actor="t", **kwargs
    )


def test_leads_unauthenticated_401(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    lead = _seed_lead(session, tenant.id)
    lid = lead["id"]
    client = _client_for(session, session_settings)
    try:
        assert client.get(BASE).status_code == 401
        assert client.post(BASE, json={"title": "X"}).status_code == 401
        assert client.get(f"{BASE}/{lid}").status_code == 401
        assert client.patch(f"{BASE}/{lid}", json={"title": "Y"}).status_code == 401
        assert client.delete(f"{BASE}/{lid}").status_code == 401
        assert client.post(f"{BASE}/{lid}/restore").status_code == 401
        assert (
            client.post(
                f"{BASE}/{lid}/transition", json={"to_status": "QUALIFIED"}
            ).status_code
            == 401
        )
        assert client.post(f"{BASE}/{lid}/convert", json={}).status_code == 401
        assert client.get(f"{BASE}/{lid}/notes").status_code == 401
        assert client.get(f"{BASE}/pipeline/counts").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_leads_forbidden_without_permission(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    lead = _seed_lead(session, tenant.id)
    user = _user_with_permissions(
        session, tenant, email="noperm@t.test", permissions=["customers.read"]
    )
    token = _token_for(session_settings, user, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        assert client.get(BASE).status_code == 403
        assert client.post(BASE, json={"title": "X"}).status_code == 403
        assert client.get(f"{BASE}/{lead['id']}").status_code == 403
        assert client.get(f"{BASE}/pipeline/counts").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_leads_authorized_matrix(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    user = _user_with_permissions(
        session, tenant, email="leadops@t.test", permissions=ALL_LEAD_PERMS
    )
    token = _token_for(session_settings, user, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        created = client.post(
            BASE,
            json={"title": "HTTP Lead", "source": "PHONE", "priority": "HIGH"},
        )
        assert created.status_code == 201, created.text
        lid = created.json()["lead"]["id"]

        assert client.get(BASE).status_code == 200
        assert client.get(f"{BASE}/{lid}").status_code == 200
        assert client.get(f"{BASE}/pipeline/counts").status_code == 200
        assert (
            client.patch(f"{BASE}/{lid}", json={"title": "HTTP Lead 2"}).status_code
            == 200
        )
        assert (
            client.post(
                f"{BASE}/{lid}/transition", json={"to_status": "QUALIFIED"}
            ).status_code
            == 200
        )
        note = client.post(f"{BASE}/{lid}/notes", json={"body": "Called"})
        assert note.status_code == 201
        nid = note.json()["note"]["id"]
        assert (
            client.patch(
                f"{BASE}/{lid}/notes/{nid}", json={"body": "Followed up"}
            ).status_code
            == 200
        )
        assert client.get(f"{BASE}/{lid}/notes").status_code == 200
        assert client.get(f"{BASE}/{lid}/activities").status_code == 200
        assert client.delete(f"{BASE}/{lid}/notes/{nid}").status_code == 200

        conv = client.post(
            f"{BASE}/{lid}/convert",
            json={
                "create_customer": {
                    "name": "HTTP Cust",
                    "phone": "+15555550123",
                }
            },
        )
        assert conv.status_code == 200
        assert conv.json()["already_converted"] is False
        again = client.post(
            f"{BASE}/{lid}/convert",
            json={"create_customer": {"name": "HTTP Cust", "phone": "+15555550123"}},
        )
        assert again.status_code == 200
        assert again.json()["already_converted"] is True

        assert client.delete(f"{BASE}/{lid}").status_code == 200
        assert client.post(f"{BASE}/{lid}/restore").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_ai_agent_lead_permissions(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    ai = _ai_user(session, tenant)
    token = _token_for(session_settings, ai, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        created = client.post(BASE, json={"title": "AI Lead", "source": "AI_AGENT"})
        assert created.status_code == 201, created.text
        lid = created.json()["lead"]["id"]

        assert client.get(BASE).status_code == 200
        assert client.get(f"{BASE}/{lid}").status_code == 200
        assert (
            client.patch(f"{BASE}/{lid}", json={"description": "noted"}).status_code
            == 200
        )
        assert (
            client.post(
                f"{BASE}/{lid}/transition", json={"to_status": "QUALIFIED"}
            ).status_code
            == 200
        )
        assert (
            client.post(f"{BASE}/{lid}/notes", json={"body": "AI note"}).status_code
            == 201
        )
        assert client.get(f"{BASE}/{lid}/notes").status_code == 200

        # High-impact ops denied for AI Agent template.
        assert (
            client.post(
                f"{BASE}/{lid}/convert",
                json={"create_customer": {"name": "X", "phone": "+15555550999"}},
            ).status_code
            == 403
        )
        assert client.delete(f"{BASE}/{lid}").status_code == 403
        owner = TenantUser(
            tenant_id=tenant.id,
            email="own@t.test",
            password_hash="x",
            name="Own",
            role="admin",
            status=MEMBERSHIP_ACTIVE,
            is_active=True,
        )
        session.add(owner)
        session.flush()
        assert (
            client.patch(
                f"{BASE}/{lid}", json={"owner_user_id": str(owner.id)}
            ).status_code
            == 403
        )
    finally:
        app.dependency_overrides.clear()


def test_leads_idor_cross_tenant_http(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    lead_b = _seed_lead(session, other.id, title="Secret B")
    note_b = LeadService(session).notes.create(
        other.id, uuid.UUID(lead_b["id"]), body="secret", actor="t"
    )
    svc_b = ServicesPricebookService(session).create_service(
        other.id, name="Other Svc", actor="t"
    )
    prod_b = ProductCatalogService(session).create(
        other.id, name="Other Prod", actor="t"
    )
    owner_b = TenantUser(
        tenant_id=other.id,
        email="b@other.test",
        password_hash="x",
        name="B",
        role="admin",
        status=MEMBERSHIP_ACTIVE,
        is_active=True,
    )
    session.add(owner_b)
    session.flush()

    user = _user_with_permissions(
        session, tenant, email="idor@t.test", permissions=ALL_LEAD_PERMS
    )
    token = _token_for(session_settings, user, tenant)
    client = _client_for(session, session_settings, token=token)
    lid = lead_b["id"]
    try:
        assert client.get(f"{BASE}/{lid}").status_code == 404
        assert client.patch(f"{BASE}/{lid}", json={"title": "Hack"}).status_code == 404
        assert client.delete(f"{BASE}/{lid}").status_code == 404
        assert client.post(f"{BASE}/{lid}/restore").status_code == 404
        assert (
            client.post(
                f"{BASE}/{lid}/transition", json={"to_status": "QUALIFIED"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"{BASE}/{lid}/convert",
                json={"create_customer": {"name": "X", "phone": "+15555550888"}},
            ).status_code
            == 404
        )
        assert client.post(f"{BASE}/{lid}/notes", json={"body": "x"}).status_code == 404
        assert (
            client.patch(
                f"{BASE}/{lid}/notes/{note_b['id']}", json={"body": "y"}
            ).status_code
            == 404
        )

        # Cross-tenant references on create/update
        bad_svc = client.post(
            BASE,
            json={"title": "Bad", "service_id": svc_b["id"]},
        )
        assert bad_svc.status_code in {400, 404}
        bad_prod = client.post(
            BASE,
            json={"title": "Bad", "product_id": prod_b["id"]},
        )
        assert bad_prod.status_code in {400, 404}
        bad_owner = client.post(
            BASE,
            json={"title": "Bad", "owner_user_id": str(owner_b.id)},
        )
        assert bad_owner.status_code in {400, 403, 404}

        # Pipeline counts must not include tenant B
        counts = client.get(f"{BASE}/pipeline/counts")
        assert counts.status_code == 200
        assert counts.json()["total"] == 0
    finally:
        app.dependency_overrides.clear()
