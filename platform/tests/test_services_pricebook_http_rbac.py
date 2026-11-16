"""HTTP-level RBAC and IDOR tests for Services & Pricebook APIs."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.crm.services import ServicesPricebookService
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.rbac.catalog import SYSTEM_ROLE_AI_AGENT
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-services-rbac-ok32",
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
        name=f"SvcLimited-{uuid.uuid4().hex[:6]}",
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


def _seed(session: Session, tenant_id: uuid.UUID) -> dict[str, str]:
    api = ServicesPricebookService(session)
    cat = api.categories.create(tenant_id, name="HVAC", actor="t")
    svc = api.create_service(
        tenant_id,
        name="Tune-Up",
        code=f"T-{uuid.uuid4().hex[:6]}",
        category_id=uuid.UUID(cat["id"]),
        base_price="100",
        actor="t",
    )
    pb = api.pricebooks.create(
        tenant_id, name=f"Std-{uuid.uuid4().hex[:4]}", is_default=True, actor="t"
    )
    item = api.pricebooks.create_item(
        tenant_id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="120",
        actor="t",
    )
    session.flush()
    return {
        "category_id": cat["id"],
        "service_id": svc["id"],
        "pricebook_id": pb["id"],
        "item_id": item["id"],
    }


def test_services_unauthenticated_401(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    client = _client_for(session, session_settings)
    try:
        assert client.get("/api/admin/crm/services").status_code == 401
        assert client.get("/api/admin/crm/service-categories").status_code == 401
        assert client.get("/api/admin/crm/pricebooks").status_code == 401
        assert (
            client.post("/api/admin/crm/services", json={"name": "X"}).status_code
            == 401
        )
    finally:
        app.dependency_overrides.clear()


def test_services_forbidden_without_permission(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    user = _user_with_permissions(
        session, tenant, email="noperm@t.test", permissions=["customers.read"]
    )
    token = _token_for(session_settings, user, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        assert client.get("/api/admin/crm/services").status_code == 403
        assert client.get("/api/admin/crm/service-categories").status_code == 403
        assert client.get("/api/admin/crm/pricebooks").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_services_authorized_crud_and_pricing(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    ids = _seed(session, tenant.id)
    user = _user_with_permissions(
        session,
        tenant,
        email="svc@t.test",
        permissions=[
            "services.read",
            "services.create",
            "services.update",
            "services.delete",
            "service_categories.read",
            "service_categories.create",
            "service_categories.update",
            "service_categories.delete",
            "pricebooks.read",
            "pricebooks.create",
            "pricebooks.update",
            "pricebooks.delete",
            "pricebook_items.read",
            "pricebook_items.create",
            "pricebook_items.update",
            "pricebook_items.delete",
        ],
    )
    token = _token_for(session_settings, user, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        assert client.get("/api/admin/crm/services").status_code == 200
        assert (
            client.get(f"/api/admin/crm/services/{ids['service_id']}").status_code
            == 200
        )
        pricing = client.get(f"/api/admin/crm/services/{ids['service_id']}/pricing")
        assert pricing.status_code == 200
        assert pricing.json()["source"] in {
            "pricebook_item",
            "organization_override",
            "service_base",
            "no_price",
        }
        created = client.post(
            "/api/admin/crm/services",
            json={"name": "New Svc", "code": f"N-{uuid.uuid4().hex[:5]}"},
        )
        assert created.status_code == 201
        sid = created.json()["id"]
        assert (
            client.patch(
                f"/api/admin/crm/services/{sid}", json={"name": "Renamed"}
            ).status_code
            == 200
        )
        assert client.delete(f"/api/admin/crm/services/{sid}").status_code == 200
        assert client.post(f"/api/admin/crm/services/{sid}/restore").status_code == 200

        assert client.get("/api/admin/crm/service-categories/tree").status_code == 200
        assert client.get("/api/admin/crm/pricebooks").status_code == 200
        assert (
            client.get(
                f"/api/admin/crm/pricebooks/{ids['pricebook_id']}/items"
            ).status_code
            == 200
        )
    finally:
        app.dependency_overrides.clear()


def test_ai_agent_read_only_services_pricebook(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    ids = _seed(session, tenant.id)
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
    token = _token_for(session_settings, ai_user, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        assert client.get("/api/admin/crm/services").status_code == 200
        assert client.get("/api/admin/crm/pricebooks").status_code == 200
        assert (
            client.get(
                f"/api/admin/crm/pricebooks/{ids['pricebook_id']}/items"
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/admin/crm/services/{ids['service_id']}/pricing"
            ).status_code
            == 200
        )
        assert (
            client.post("/api/admin/crm/services", json={"name": "Nope"}).status_code
            == 403
        )
        assert (
            client.post("/api/admin/crm/pricebooks", json={"name": "Nope"}).status_code
            == 403
        )
        assert (
            client.delete(f"/api/admin/crm/services/{ids['service_id']}").status_code
            == 403
        )
        # Categories: AI does not get service_categories.read by default
        assert client.get("/api/admin/crm/service-categories").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_idor_cross_tenant_http(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    ids_a = _seed(session, tenant.id)
    ids_b = _seed(session, other.id)
    catalog = ProductCatalogService(session)
    prod_b = catalog.create(
        other.id, name="Pipe", sku=f"P-{uuid.uuid4().hex[:5]}", price="1", actor="t"
    )
    var_b = catalog.variants.create(
        other.id, uuid.UUID(prod_b["id"]), sku=f"P-{uuid.uuid4().hex[:5]}-A", actor="t"
    )
    session.flush()

    user = _user_with_permissions(
        session,
        tenant,
        email="idor@t.test",
        permissions=[
            "services.read",
            "services.update",
            "services.delete",
            "service_categories.read",
            "service_categories.update",
            "pricebooks.read",
            "pricebooks.update",
            "pricebooks.delete",
            "pricebook_items.read",
            "pricebook_items.create",
            "pricebook_items.update",
            "pricebook_items.delete",
        ],
    )
    token = _token_for(session_settings, user, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        assert (
            client.get(f"/api/admin/crm/services/{ids_b['service_id']}").status_code
            == 404
        )
        assert (
            client.patch(
                f"/api/admin/crm/services/{ids_b['service_id']}",
                json={"name": "Hack"},
            ).status_code
            == 404
        )
        assert (
            client.delete(f"/api/admin/crm/services/{ids_b['service_id']}").status_code
            == 404
        )
        assert (
            client.get(f"/api/admin/crm/pricebooks/{ids_b['pricebook_id']}").status_code
            == 404
        )
        assert (
            client.get(
                f"/api/admin/crm/services/{ids_b['service_id']}/pricing"
            ).status_code
            == 404
        )
        # Free the service slot then attempt cross-tenant material reference
        assert (
            client.delete(
                f"/api/admin/crm/pricebooks/{ids_a['pricebook_id']}/items/"
                f"{ids_a['item_id']}"
            ).status_code
            == 200
        )
        bad = client.post(
            f"/api/admin/crm/pricebooks/{ids_a['pricebook_id']}/items",
            json={
                "service_id": ids_a["service_id"],
                "pricing_type": "FIXED",
                "price": "1",
                "components": [
                    {
                        "component_type": "MATERIAL",
                        "product_variant_id": var_b["id"],
                        "quantity": "1",
                    }
                ],
            },
        )
        assert bad.status_code in {400, 409}
        assert bad.json()["detail"]["code"] == "invalid_variant"
    finally:
        app.dependency_overrides.clear()
