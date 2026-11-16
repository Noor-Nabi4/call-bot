"""Geo reference catalog seed, relations, and API tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.api import deps as api_deps
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.geo import GeoCountry, GeoRegion
from callbot_platform.geo.seed import ensure_geo_catalog
from callbot_platform.geo.service import GeoCatalogError, GeoCatalogService
from callbot_platform.main import app
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        session_secret="geo-catalog-session-secret-for-tests-ok",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
    )


@pytest.fixture()
def client(session: Session, settings: Settings) -> Generator[TestClient, None, None]:
    def _db() -> Generator[Session, None, None]:
        yield session

    def _settings() -> Settings:
        return settings

    app.dependency_overrides[api_deps.db_dep] = _db
    app.dependency_overrides[api_deps.settings_dep] = _settings
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def test_ensure_geo_catalog_idempotent(session: Session) -> None:
    from callbot_platform.geo.cache import clear_catalog_cache, get_cached_catalog
    from callbot_platform.geo.service import GeoCatalogService

    clear_catalog_cache()
    first = ensure_geo_catalog(session)
    session.commit()
    assert first["countries"] >= 200
    assert first["regions"] >= 1000
    assert first["currencies"] >= 100
    assert first["timezones"] >= 100
    assert get_cached_catalog() is None

    second = ensure_geo_catalog(session)
    session.commit()
    assert second == first

    svc = GeoCatalogService(session)
    payload = svc.catalog_payload()
    assert get_cached_catalog() is not None
    assert svc.catalog_payload() is get_cached_catalog()
    assert payload["countries"]

    pk = session.get(GeoCountry, "PK")
    assert pk is not None
    assert pk.name == "Pakistan"
    regions = session.scalar(
        select(func.count())
        .select_from(GeoRegion)
        .where(GeoRegion.country_code == "PK")
    )
    assert regions is not None and regions >= 5


def test_geo_service_regions_and_validation(session: Session) -> None:
    ensure_geo_catalog(session)
    session.commit()
    svc = GeoCatalogService(session)

    catalog = svc.catalog_payload()
    us = next(c for c in catalog["countries"] if c["key"] == "US")
    assert us["default_currency_code"] == "USD"
    usd = next(c for c in catalog["currencies"] if c["key"] == "USD")
    assert usd["symbol"] == "$"
    assert usd["name"] == "US Dollar"
    assert any(t["key"] == "UTC" for t in catalog["timezones"])

    regions = svc.regions_payload("pk")
    assert regions["country"] == "PK"
    assert any(r["key"] == "PB" for r in regions["regions"])

    ok = svc.normalize_and_validate_profile_fields(
        country="Pakistan",
        state="Punjab",
        currency="pkr",
        timezone="Asia/Karachi",
    )
    assert ok["country"] == "PK"
    assert ok["state"] == "PB"
    assert ok["currency"] == "PKR"
    assert ok["timezone"] == "Asia/Karachi"

    with pytest.raises(GeoCatalogError) as exc:
        svc.normalize_and_validate_profile_fields(country="ZZ")
    assert exc.value.code == "unknown_country"

    with pytest.raises(GeoCatalogError) as exc2:
        svc.normalize_and_validate_profile_fields(country="PK", state="NOTREAL")
    assert exc2.value.code == "unknown_region"

    state_only = svc.normalize_and_validate_profile_fields(
        state="Sindh",
        existing_country="PK",
    )
    assert state_only["state"] == "SD"

    with pytest.raises(GeoCatalogError) as exc3:
        svc.normalize_and_validate_profile_fields(
            state="NOTREAL",
            existing_country="PK",
        )
    assert exc3.value.code == "unknown_region"


def test_public_geo_endpoints(client: TestClient, session: Session) -> None:
    ensure_geo_catalog(session)
    session.commit()

    catalog = client.get("/geo/catalog")
    assert catalog.status_code == 200
    body = catalog.json()
    assert len(body["countries"]) >= 200
    assert len(body["currencies"]) >= 100

    regions = client.get("/geo/regions", params={"country": "US"})
    assert regions.status_code == 200
    assert regions.json()["country"] == "US"
    assert any(r["key"] == "CA" for r in regions.json()["regions"])


def test_business_profile_includes_geo_catalogs_and_validates(
    client: TestClient, session: Session, settings: Settings, tenant: Tenant
) -> None:
    ensure_geo_catalog(session)
    ensure_system_roles_for_tenant(session, tenant.id)
    user = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email=f"geo-{uuid.uuid4().hex[:8]}@example.com",
        password="password12345",
        name="Geo Admin",
    )
    session.commit()
    token = create_session_token(
        settings=settings,
        user_id=uuid.UUID(str(user["id"])),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )
    client.cookies.set(settings.session_cookie_name, token)

    got = client.get("/api/admin/organization/business-profile")
    assert got.status_code == 200
    catalogs = got.json()["catalogs"]
    assert len(catalogs["countries"]) >= 200
    assert len(catalogs["timezones"]) >= 100

    bad = client.patch(
        "/api/admin/organization/business-profile",
        json={"country": "ZZ"},
    )
    assert bad.status_code in {400, 404}
    assert bad.json()["detail"]["code"] == "unknown_country"

    ok = client.patch(
        "/api/admin/organization/business-profile",
        json={
            "country": "PK",
            "state": "PB",
            "currency": "PKR",
            "timezone": "Asia/Karachi",
        },
    )
    assert ok.status_code == 200
    profile = ok.json()["profile"]
    assert profile["country"] == "PK"
    assert profile["state"] == "PB"
    assert profile["currency"] == "PKR"
