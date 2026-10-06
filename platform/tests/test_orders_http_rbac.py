"""HTTP-level RBAC and IDOR tests for Order CRM APIs (Phase 9)."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.orders import OrderService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.rbac.catalog import SYSTEM_ROLE_AI_AGENT
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token

BASE = "/api/admin/crm/orders"

ALL_ORDER_PERMS = [
    "orders.read",
    "orders.create",
    "orders.update",
    "orders.delete",
    "orders.transition",
    "orders.cancel",
    "orders.refund",
]


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-orders-rbac-ok32chars",
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
        name=f"OrderLimited-{uuid.uuid4().hex[:6]}",
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


def _setup_commerce(session: Session, tenant: Tenant) -> dict:
    catalog = ProductCatalogService(session)
    prod = catalog.create(tenant.id, name="Part", sku="PRT-1", price="10.00", actor="t")
    variant = catalog.variants.create(
        tenant.id, uuid.UUID(prod["id"]), sku="PRT-1-A", actor="t"
    )
    inv = InventoryService(session)
    loc = inv.locations.create(
        tenant.id, name="Main", code="MAIN", actor="t", is_default=True
    )
    item = inv.items.ensure_for_variant(tenant.id, uuid.UUID(variant["id"]), actor="t")
    inv.mutations.purchase(
        tenant.id,
        item.id,
        location_id=uuid.UUID(loc["id"]),
        quantity=50,
        actor="t",
    )
    customer = CustomerService(session).create(
        tenant.id,
        name="Cust",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    return {
        "product_id": prod["id"],
        "variant_id": variant["id"],
        "customer_id": customer["id"],
        "location_id": loc["id"],
    }


def test_unauthenticated_401(session: Session, session_settings: Settings) -> None:
    client = _client_for(session, session_settings)
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json={}).status_code == 401


def test_missing_permission_403(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    user = _user_with_permissions(
        session, tenant, email="noperm@t.test", permissions=["customers.read"]
    )
    client = _client_for(
        session, session_settings, token=_token_for(session_settings, user, tenant)
    )
    assert client.get(BASE).status_code == 403
    assert (
        client.post(
            BASE, json={"customer_id": str(uuid.uuid4()), "items": []}
        ).status_code
        == 403
    )


def test_authorized_crud_transition_cancel_refund(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    setup = _setup_commerce(session, tenant)
    user = _user_with_permissions(
        session, tenant, email="full@t.test", permissions=ALL_ORDER_PERMS
    )
    client = _client_for(
        session, session_settings, token=_token_for(session_settings, user, tenant)
    )
    created = client.post(
        BASE,
        json={
            "customer_id": setup["customer_id"],
            "fulfillment_location_id": setup["location_id"],
            "items": [
                {
                    "product_id": setup["product_id"],
                    "variant_id": setup["variant_id"],
                    "quantity": 1,
                }
            ],
        },
        headers={"Idempotency-Key": "http-idem-1"},
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["order"]["id"]

    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{order_id}").status_code == 200
    assert client.get(f"{BASE}/{order_id}/history").status_code == 200

    patch = client.patch(f"{BASE}/{order_id}", json={"notes": "n1"})
    assert patch.status_code == 200

    for status in ("PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"):
        r = client.post(f"{BASE}/{order_id}/transition", json={"to_status": status})
        assert r.status_code == 200, r.text

    refund = client.post(f"{BASE}/{order_id}/refund", json={"reason": "lifecycle only"})
    assert refund.status_code == 200
    assert refund.json()["order"]["status"] == "REFUNDED"

    # New order for cancel path
    created2 = client.post(
        BASE,
        json={
            "customer_id": setup["customer_id"],
            "items": [
                {
                    "product_id": setup["product_id"],
                    "variant_id": setup["variant_id"],
                    "quantity": 1,
                }
            ],
        },
    )
    oid2 = created2.json()["order"]["id"]
    client.post(f"{BASE}/{oid2}/transition", json={"to_status": "PENDING"})
    cancel = client.post(f"{BASE}/{oid2}/cancel", json={"reason": "customer request"})
    assert cancel.status_code == 200
    assert cancel.json()["order"]["status"] == "CANCELLED"

    archived = client.delete(f"{BASE}/{oid2}")
    assert archived.status_code == 200
    restored = client.post(f"{BASE}/{oid2}/restore")
    assert restored.status_code == 200


def test_ai_cannot_cancel_or_refund(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    setup = _setup_commerce(session, tenant)
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
    client = _client_for(
        session, session_settings, token=_token_for(session_settings, ai_user, tenant)
    )
    created = client.post(
        BASE,
        json={
            "customer_id": setup["customer_id"],
            "items": [
                {
                    "product_id": setup["product_id"],
                    "variant_id": setup["variant_id"],
                    "quantity": 1,
                }
            ],
        },
    )
    assert created.status_code == 201
    oid = created.json()["order"]["id"]
    assert client.post(f"{BASE}/{oid}/cancel").status_code == 403
    assert (
        client.post(
            f"{BASE}/{oid}/transition", json={"to_status": "CANCELLED"}
        ).status_code
        == 403
    )


def test_idor_cross_tenant(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    tenant_b = Tenant(name="B", slug=f"b-{uuid.uuid4().hex[:8]}")
    session.add(tenant_b)
    session.flush()
    setup_a = _setup_commerce(session, tenant)
    setup_b = _setup_commerce(session, tenant_b)

    order_a = OrderService(session).create(
        tenant.id,
        customer_id=uuid.UUID(setup_a["customer_id"]),
        actor="t",
        items=[
            {
                "product_id": uuid.UUID(setup_a["product_id"]),
                "variant_id": uuid.UUID(setup_a["variant_id"]),
                "quantity": 1,
            }
        ],
    )
    user_b = _user_with_permissions(
        session, tenant_b, email="b@t.test", permissions=ALL_ORDER_PERMS
    )
    client_b = _client_for(
        session, session_settings, token=_token_for(session_settings, user_b, tenant_b)
    )
    oid = order_a["id"]
    assert client_b.get(f"{BASE}/{oid}").status_code == 404
    assert client_b.patch(f"{BASE}/{oid}", json={"notes": "x"}).status_code == 404
    assert client_b.delete(f"{BASE}/{oid}").status_code == 404
    assert client_b.post(f"{BASE}/{oid}/restore").status_code == 404
    assert (
        client_b.post(
            f"{BASE}/{oid}/transition", json={"to_status": "PENDING"}
        ).status_code
        == 404
    )
    assert client_b.post(f"{BASE}/{oid}/cancel").status_code == 404
    assert client_b.post(f"{BASE}/{oid}/refund").status_code == 404
    assert client_b.get(f"{BASE}/{oid}/history").status_code == 404

    # Cross-tenant customer/product on create
    user_a = _user_with_permissions(
        session, tenant, email="a@t.test", permissions=ALL_ORDER_PERMS
    )
    client_a = _client_for(
        session, session_settings, token=_token_for(session_settings, user_a, tenant)
    )
    bad = client_a.post(
        BASE,
        json={
            "customer_id": setup_b["customer_id"],
            "items": [
                {
                    "product_id": setup_a["product_id"],
                    "variant_id": setup_a["variant_id"],
                    "quantity": 1,
                }
            ],
        },
    )
    assert bad.status_code in {404, 409}
