"""HTTP RBAC / IDOR for Phase 13 Estimates APIs."""

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
from callbot_platform.crm.estimates import EstimateService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.rbac.catalog import SYSTEM_ROLE_AI_AGENT
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token

BASE = "/api/admin/crm/estimates"


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-estimates-rbac-ok32c",
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


def test_estimate_http_happy_and_idor(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    token = _admin_token(session, session_settings, tenant)
    customer = CustomerService(session).create(
        tenant.id, name="C", phone="+15551234567", actor="t"
    )
    prod = ProductCatalogService(session).create(
        tenant.id, name="P", sku=f"S-{uuid.uuid4().hex[:6]}", price="10", actor="t"
    )
    client = _client_for(session, session_settings, token=token)
    created = client.post(
        BASE,
        json={
            "customer_id": customer["id"],
            "items": [
                {
                    "item_type": "PRODUCT",
                    "product_id": prod["id"],
                    "quantity": 1,
                }
            ],
            "valid_until": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    eid = created.json()["estimate"]["id"]
    assert client.post(f"{BASE}/{eid}/send").status_code == 200
    assert client.post(f"{BASE}/{eid}/approve").status_code == 200

    other = Tenant(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    ensure_system_roles_for_tenant(session, other.id)
    other_admin = AuthRepository(session).bootstrap_admin(
        tenant_id=other.id,
        email=f"o-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Other",
    )
    other_token = create_session_token(
        settings=session_settings,
        user_id=uuid.UUID(other_admin["id"]),
        tenant_id=other.id,
        role=other_admin["role"],
        email=other_admin["email"],
    )
    other_client = _client_for(session, session_settings, token=other_token)
    assert other_client.get(f"{BASE}/{eid}").status_code in {403, 404}
    assert other_client.post(f"{BASE}/{eid}/approve").status_code in {403, 404}


def test_ai_cannot_approve_or_convert(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    ensure_system_roles_for_tenant(session, tenant.id)
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email=f"owner-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Owner",
    )
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
    for r in roles.list_member_roles(tenant.id, uuid.UUID(ai_user["id"]))["roles"]:
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
    customer = CustomerService(session).create(
        tenant.id, name="C", phone="+15557654321", actor="t"
    )
    est = EstimateService(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        actor="t",
        items=[
            {
                "item_type": "CUSTOM",
                "name": "X",
                "unit_price": "5",
                "quantity": "1",
            }
        ],
    )
    EstimateService(session).send(tenant.id, uuid.UUID(est["id"]), actor="t")
    token = create_session_token(
        settings=session_settings,
        user_id=uuid.UUID(ai_user["id"]),
        tenant_id=tenant.id,
        role=ai_user["role"],
        email=ai_user["email"],
    )
    client = _client_for(session, session_settings, token=token)
    assert client.get(f"{BASE}/{est['id']}").status_code == 200
    assert client.post(f"{BASE}/{est['id']}/approve").status_code == 403
    assert (
        client.post(
            f"{BASE}/{est['id']}/convert", json={"target_type": "JOB"}
        ).status_code
        == 403
    )
