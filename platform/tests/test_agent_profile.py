"""CRM agent-settings / agent-profile repository and API tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, require_internal_token
from callbot_platform.config import get_settings
from callbot_platform.crm.repos import AgentSettingsRepository
from callbot_platform.db.models import Tenant
from callbot_platform.main import app


def test_agent_profile_missing_fail_closed(session: Session, tenant: Tenant) -> None:
    assert (
        AgentSettingsRepository(session).get_profile(
            tenant.id, business_name=tenant.name
        )
        is None
    )


def test_agent_profile_round_trip(session: Session, tenant: Tenant) -> None:
    repo = AgentSettingsRepository(session)
    created = repo.upsert(
        tenant.id,
        language="en",
        greeting="Thanks for calling",
        assistant_name="Riley",
        business_hours_summary="Weekdays 8 to 6",
        service_areas=["Austin"],
        response_style="concise",
        custom_instructions="Be brief.",
        supported_languages=["en", "es"],
    )
    assert created["profile_version"] == 1
    updated = repo.upsert(tenant.id, tone="warm")
    assert updated["profile_version"] == 2
    profile = repo.get_profile(tenant.id, business_name=tenant.name)
    assert profile is not None
    assert profile["business_name"] == tenant.name
    assert profile["assistant_name"] == "Riley"
    assert profile["service_areas"] == ["Austin"]
    assert profile["profile_version"] == 2
    assert "en" in profile["supported_languages"]


def test_internal_agent_profile_endpoint(session: Session, tenant: Tenant) -> None:
    AgentSettingsRepository(session).upsert(
        tenant.id,
        greeting="Hi",
        business_hours_summary="9-5",
        language="en",
    )
    session.flush()

    no_settings_tenant = Tenant(
        name="No Settings Co", slug=f"noset-{uuid.uuid4().hex[:8]}"
    )
    session.add(no_settings_tenant)
    session.flush()

    def _db_override() -> Generator[Session, None, None]:
        yield session

    def _token_ok() -> None:
        return None

    app.dependency_overrides[db_dep] = _db_override
    app.dependency_overrides[require_internal_token] = _token_ok
    try:
        client = TestClient(app)
        missing = client.get(f"/internal/tenants/{uuid.uuid4()}/agent-profile")
        assert missing.status_code == 404

        empty = client.get(f"/internal/tenants/{no_settings_tenant.id}/agent-profile")
        assert empty.status_code == 404
        assert empty.json()["detail"]["code"] == "agent_profile_missing"

        ok = client.get(f"/internal/tenants/{tenant.id}/agent-profile")
        assert ok.status_code == 200
        profile = ok.json()["profile"]
        assert profile["business_name"] == tenant.name
        assert profile["business_hours_summary"] == "9-5"
    finally:
        app.dependency_overrides.clear()


def test_internal_agent_profile_requires_token(
    session: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "expected-token")
    get_settings.cache_clear()
    AgentSettingsRepository(session).upsert(tenant.id, greeting="Hi", language="en")
    session.flush()

    def _db_override() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[db_dep] = _db_override
    try:
        client = TestClient(app)
        unauthorized = client.get(f"/internal/tenants/{tenant.id}/agent-profile")
        assert unauthorized.status_code == 401
        authorized = client.get(
            f"/internal/tenants/{tenant.id}/agent-profile",
            headers={"X-Internal-Token": "expected-token"},
        )
        assert authorized.status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
