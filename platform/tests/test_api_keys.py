"""Tenant API key and /v1 public API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api_keys import ApiKeyRepository
from callbot_platform.crm.repos import CustomerRepository
from callbot_platform.db.models import Tenant
from callbot_platform.main import app


def test_api_key_auth_lists_customers(session: Session, tenant: Tenant) -> None:
    CustomerRepository(session).upsert(
        tenant.id, name="Public API Cust", phone="+15551230000"
    )
    repo = ApiKeyRepository(session)
    created = repo.create_key(
        tenant.id,
        name="CI",
        scopes=["customers:read", "calls:read"],
        actor="admin@t.test",
    )
    secret = created["secret"]
    assert secret.startswith("cbk_")
    assert created["key_prefix"].startswith("cbk_")

    # Override db for TestClient
    from callbot_platform.api import deps as api_deps

    def _db():
        yield session

    app.dependency_overrides[api_deps.db_dep] = _db
    client = TestClient(app)
    try:
        denied = client.get("/v1/customers")
        assert denied.status_code == 401

        ok = client.get(
            "/v1/customers",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert ok.status_code == 200, ok.text
        assert any(c["name"] == "Public API Cust" for c in ok.json()["customers"])

        calls = client.get(
            "/v1/calls",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert calls.status_code == 200

        # Scope enforcement
        narrow = repo.create_key(
            tenant.id, name="Calls only", scopes=["calls:read"], actor="admin@t.test"
        )
        blocked = client.get(
            "/v1/customers",
            headers={"Authorization": f"Bearer {narrow['secret']}"},
        )
        assert blocked.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_revoke_api_key(session: Session, tenant: Tenant) -> None:
    repo = ApiKeyRepository(session)
    created = repo.create_key(tenant.id, name="Temp", actor="admin@t.test")
    from uuid import UUID

    revoked = repo.revoke_key(tenant.id, UUID(created["id"]), actor="admin@t.test")
    assert revoked["is_active"] is False
    assert repo.authenticate(created["secret"]) is None
