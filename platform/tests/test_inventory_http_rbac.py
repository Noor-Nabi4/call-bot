"""HTTP-level RBAC and IDOR tests for inventory APIs."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.rbac.catalog import SYSTEM_ROLE_AI_AGENT, SYSTEM_ROLE_OWNER
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-inventory-rbac-ok32",
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


def _seed_inventory(session: Session, tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    catalog = ProductCatalogService(session)
    prod = catalog.create(
        tenant_id, name="Bolt", sku=f"B-{uuid.uuid4().hex[:6]}", price="2", actor="t"
    )
    variant = catalog.variants.create(
        tenant_id,
        uuid.UUID(prod["id"]),
        sku=f"B-{uuid.uuid4().hex[:6]}-A",
        actor="t",
    )
    inv = InventoryService(session)
    loc = inv.locations.create(
        tenant_id, name="Yard", code=f"Y{uuid.uuid4().hex[:4]}", actor="t", is_default=True
    )
    item = inv.items.ensure_for_variant(
        tenant_id, uuid.UUID(variant["id"]), actor="t"
    )
    inv.mutations.purchase(
        tenant_id,
        item.id,
        location_id=uuid.UUID(loc["id"]),
        quantity=20,
        actor="t",
    )
    session.flush()
    return {
        "item_id": item.id,
        "location_id": uuid.UUID(loc["id"]),
        "variant_id": uuid.UUID(variant["id"]),
    }


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
    # Replace member roles with a custom role holding only requested permissions.
    roles = RoleRepository(session)
    custom = roles.create_role(
        tenant.id,
        name=f"InvLimited-{uuid.uuid4().hex[:6]}",
        description="test",
        permissions=[
            {"key": k, "scope": "ALL_ORGANIZATION"} for k in permissions
        ],
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
    )
    # Clear existing roles then assign custom.
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


def test_inventory_unauthenticated_401(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    client = _client_for(session, session_settings)
    try:
        assert client.get("/api/admin/crm/inventory").status_code == 401
        assert client.get("/api/admin/crm/inventory/locations").status_code == 401
        assert (
            client.post(
                f"/api/admin/crm/inventory/{uuid.uuid4()}/purchase",
                json={"location_id": str(uuid.uuid4()), "quantity": 1},
            ).status_code
            == 401
        )
    finally:
        app.dependency_overrides.clear()


def test_inventory_read_forbidden_without_permission(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    user = _user_with_permissions(
        session, tenant, email="noperm@t.test", permissions=["customers.read"]
    )
    token = _token_for(session_settings, user, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.get("/api/admin/crm/inventory")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_inventory_owner_can_mutate(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    ids = _seed_inventory(session, tenant.id)
    token = _token_for(session_settings, owner, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        listed = client.get("/api/admin/crm/inventory")
        assert listed.status_code == 200
        assert "inventory" in listed.json()

        detail = client.get(f"/api/admin/crm/inventory/{ids['item_id']}")
        assert detail.status_code == 200

        txns = client.get(f"/api/admin/crm/inventory/{ids['item_id']}/transactions")
        assert txns.status_code == 200

        body = {
            "location_id": str(ids["location_id"]),
            "quantity": 1,
            "reason": "cycle",
        }
        for action in ("purchase", "sale", "adjust", "return", "reserve", "release"):
            # release needs reserved qty — reserve first already in loop order after purchase
            if action == "release":
                client.post(
                    f"/api/admin/crm/inventory/{ids['item_id']}/reserve",
                    json={"location_id": str(ids["location_id"]), "quantity": 2},
                    headers={"Idempotency-Key": f"pre-rel-{uuid.uuid4().hex}"},
                )
            payload = dict(body)
            if action != "adjust":
                payload.pop("reason", None)
            res = client.post(
                f"/api/admin/crm/inventory/{ids['item_id']}/{action}",
                json=payload,
                headers={"Idempotency-Key": f"{action}-{uuid.uuid4().hex}"},
            )
            assert res.status_code == 200, (action, res.status_code, res.text)

        min_res = client.patch(
            f"/api/admin/crm/inventory/{ids['item_id']}/minimum-stock",
            json={"location_id": str(ids["location_id"]), "minimum_stock": 2},
        )
        assert min_res.status_code == 200

        loc_create = client.post(
            "/api/admin/crm/inventory/locations",
            json={"name": "Van 1", "code": "VAN1", "location_type": "VEHICLE"},
        )
        assert loc_create.status_code == 200
        loc_id = loc_create.json()["id"]
        assert client.get(f"/api/admin/crm/inventory/locations/{loc_id}").status_code == 200
        assert (
            client.patch(
                f"/api/admin/crm/inventory/locations/{loc_id}",
                json={"description": "Field van"},
            ).status_code
            == 200
        )
    finally:
        app.dependency_overrides.clear()


def test_inventory_adjust_forbidden_for_read_only(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    ids = _seed_inventory(session, tenant.id)
    user = _user_with_permissions(
        session, tenant, email="reader@t.test", permissions=["inventory.read"]
    )
    token = _token_for(session_settings, user, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        assert client.get("/api/admin/crm/inventory").status_code == 200
        res = client.post(
            f"/api/admin/crm/inventory/{ids['item_id']}/sale",
            json={"location_id": str(ids["location_id"]), "quantity": 1},
        )
        assert res.status_code == 403
        res2 = client.patch(
            f"/api/admin/crm/inventory/{ids['item_id']}/minimum-stock",
            json={"location_id": str(ids["location_id"]), "minimum_stock": 1},
        )
        assert res2.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_ai_agent_may_read_and_reserve_not_adjust(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    ids = _seed_inventory(session, tenant.id)
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    ensure_system_roles_for_tenant(session, tenant.id)
    agent = auth.create_user(
        tenant.id,
        email="ai@t.test",
        password="password123",
        name="AI",
        role="admin",
        actor=owner["email"],
    )
    roles = {r["name"]: r for r in RoleRepository(session).list_roles(tenant.id)}
    repo = RoleRepository(session)
    member_roles = repo.list_member_roles(tenant.id, uuid.UUID(agent["id"]))
    for r in member_roles["roles"]:
        repo.remove_role(
            tenant.id,
            member_id=uuid.UUID(agent["id"]),
            role_id=uuid.UUID(r["id"]),
            actor=owner["email"],
            actor_user_id=uuid.UUID(owner["id"]),
        )
    repo.assign_role(
        tenant.id,
        member_id=uuid.UUID(agent["id"]),
        role_id=uuid.UUID(roles[SYSTEM_ROLE_AI_AGENT]["id"]),
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
    )
    token = _token_for(session_settings, agent, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        assert client.get("/api/admin/crm/inventory").status_code == 200
        reserve = client.post(
            f"/api/admin/crm/inventory/{ids['item_id']}/reserve",
            json={"location_id": str(ids["location_id"]), "quantity": 1},
            headers={"Idempotency-Key": f"ai-res-{uuid.uuid4().hex}"},
        )
        assert reserve.status_code == 200
        adjust = client.post(
            f"/api/admin/crm/inventory/{ids['item_id']}/adjust",
            json={
                "location_id": str(ids["location_id"]),
                "quantity": 1,
                "reason": "nope",
            },
        )
        assert adjust.status_code == 403
        delete_loc = client.delete(
            f"/api/admin/crm/inventory/locations/{ids['location_id']}"
        )
        assert delete_loc.status_code == 403
        configure = client.patch(
            f"/api/admin/crm/inventory/{ids['item_id']}/minimum-stock",
            json={"location_id": str(ids["location_id"]), "minimum_stock": 1},
        )
        assert configure.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_inventory_cross_tenant_idor(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    auth = AuthRepository(session)
    owner_a = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="a@t.test",
        password="password123",
        name="A",
    )
    auth.bootstrap_admin(
        tenant_id=other.id,
        email="b@t.test",
        password="password123",
        name="B",
    )
    ids_a = _seed_inventory(session, tenant.id)
    ids_b = _seed_inventory(session, other.id)

    token = _token_for(session_settings, owner_a, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        # Read B's item → not found (no leak)
        assert (
            client.get(f"/api/admin/crm/inventory/{ids_b['item_id']}").status_code
            == 404
        )
        assert (
            client.get(
                f"/api/admin/crm/inventory/{ids_b['item_id']}/transactions"
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/admin/crm/inventory/locations/{ids_b['location_id']}"
            ).status_code
            == 404
        )

        # Mutate B with A's credentials
        for action in ("purchase", "sale", "reserve", "release", "return", "adjust"):
            payload: dict = {
                "location_id": str(ids_b["location_id"]),
                "quantity": 1,
            }
            if action == "adjust":
                payload["reason"] = "x"
            res = client.post(
                f"/api/admin/crm/inventory/{ids_b['item_id']}/{action}",
                json=payload,
            )
            assert res.status_code in {403, 404}, (action, res.status_code)

        # Cross-tenant reference: A item + B location
        cross = client.post(
            f"/api/admin/crm/inventory/{ids_a['item_id']}/purchase",
            json={"location_id": str(ids_b["location_id"]), "quantity": 1},
        )
        assert cross.status_code in {400, 404, 409}

        min_cross = client.patch(
            f"/api/admin/crm/inventory/{ids_b['item_id']}/minimum-stock",
            json={"location_id": str(ids_a["location_id"]), "minimum_stock": 1},
        )
        assert min_cross.status_code in {403, 404}
    finally:
        app.dependency_overrides.clear()


def test_ai_agent_default_permissions_catalog() -> None:
    from callbot_platform.rbac.catalog import default_role_permissions

    keys = {k for k, _ in default_role_permissions(SYSTEM_ROLE_AI_AGENT)}
    assert "inventory.read" in keys
    assert "inventory.reserve" in keys
    assert "inventory.adjust" not in keys
    assert "inventory.delete" not in keys
    assert "inventory.configure" not in keys
    owner_keys = {k for k, _ in default_role_permissions(SYSTEM_ROLE_OWNER)}
    assert "inventory.adjust" in owner_keys
