"""Phase 3.5 Dynamic CRM hardening tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm_config import CrmSetupService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.crm import Customer
from callbot_platform.dynamic_crm import (
    CustomObjectService,
    DynamicCrmError,
    EffectiveCrmConfigurationService,
    FieldDefinitionService,
    ModuleConfigService,
    RelationshipService,
)
from callbot_platform.dynamic_crm.config_cache import (
    clear_all_effective_configuration_cache,
)
from callbot_platform.dynamic_crm.query import apply_field_filters
from callbot_platform.main import app
from callbot_platform.organization import OrganizationService
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-crm-harden-ok32",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
    )


@pytest.fixture(autouse=True)
def _clear_crm_cache() -> Generator[None, None, None]:
    clear_all_effective_configuration_cache()
    yield
    clear_all_effective_configuration_cache()


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Harden B", slug=f"harden-b-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _seed(session: Session, tenant: Tenant) -> None:
    OrganizationService(session).update(
        tenant.id,
        actor="seed",
        name="Harden Co",
        industry="hvac",
        business_type="services",
    )
    CrmSetupService(session).setup(tenant.id, actor="seed")


def _override_db(session: Session):
    def _db() -> Generator[Session, None, None]:
        yield session

    return _db


def _client(session: Session, settings: Settings, token: str) -> TestClient:
    app.dependency_overrides[db_dep] = _override_db(session)
    app.dependency_overrides[settings_dep] = lambda: settings
    get_settings.cache_clear()
    client = TestClient(app)
    client.cookies.set(settings.session_cookie_name, token)
    return client


def _token(settings: Settings, user: dict, tenant: Tenant) -> str:
    return create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )


def test_effective_config_cache_invalidates_on_module_change(
    session: Session, tenant: Tenant
) -> None:
    _seed(session, tenant)
    svc = EffectiveCrmConfigurationService(session)
    first = svc.get(tenant.id)
    assert any(m["key"] == "JOBS" and m["enabled"] for m in first["enabled_modules"])
    ModuleConfigService(session).set_enabled(
        tenant.id, "JOBS", enabled=False, actor="a"
    )
    second = svc.get(tenant.id)
    assert all(m["key"] != "JOBS" for m in second["enabled_modules"])


def test_malicious_filter_ast_rejected(session: Session, tenant: Tenant) -> None:
    _seed(session, tenant)
    FieldDefinitionService(session).create_field(
        tenant.id,
        owner_scope="module",
        owner_key="CUSTOMERS",
        field_key="priority",
        label="Priority",
        field_type="TEXT",
        actor="a",
    )
    with pytest.raises(DynamicCrmError):
        apply_field_filters(
            session,
            tenant.id,
            owner_scope="module",
            owner_key="CUSTOMERS",
            filters=[{"field": "1=1", "operator": "equals", "value": "x"}],
        )
    with pytest.raises(DynamicCrmError):
        apply_field_filters(
            session,
            tenant.id,
            owner_scope="module",
            owner_key="CUSTOMERS",
            filters=[{"field": "priority", "operator": "raw_sql", "value": "x"}],
        )
    with pytest.raises(DynamicCrmError):
        apply_field_filters(
            session,
            tenant.id,
            owner_scope="module",
            owner_key="CUSTOMERS",
            filters=[
                {
                    "field": "priority",
                    "operator": "equals",
                    "value": "x",
                    "order_by": "DROP TABLE",
                }
            ],
        )
    # LIKE metacharacters must not match everything
    from callbot_platform.dynamic_crm.fields import FieldValueService

    rid = uuid.uuid4()
    FieldValueService(session).set_values(
        tenant.id,
        record_type="module",
        record_id=rid,
        owner_scope="module",
        owner_key="CUSTOMERS",
        values={"priority": "normal"},
        is_create=True,
    )
    found = apply_field_filters(
        session,
        tenant.id,
        owner_scope="module",
        owner_key="CUSTOMERS",
        filters=[{"field": "priority", "operator": "contains", "value": "%"}],
    )
    assert rid not in found


def test_configuration_only_relationship_rejected(
    session: Session, tenant: Tenant
) -> None:
    _seed(session, tenant)
    with pytest.raises(DynamicCrmError) as exc:
        RelationshipService(session).create_definition(
            tenant.id,
            relationship_key="customer_invoices",
            source_type="module",
            source_key="CUSTOMERS",
            target_type="module",
            target_key="INVOICES",
            cardinality="ONE_TO_MANY",
            actor="a",
        )
    assert exc.value.code == "entity_not_materialized"


def test_field_path_ownership_idor(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    _seed(session, tenant)
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="harden-a@t.test",
        password="password123",
        name="A",
    )
    obj = CustomObjectService(session).create_definition(
        tenant.id, object_key="unit", name="Unit", actor="a"
    )
    field = FieldDefinitionService(session).create_field(
        tenant.id,
        owner_scope="object",
        owner_key="unit",
        field_key="serial",
        label="Serial",
        field_type="TEXT",
        actor="a",
    )
    client = _client(session, session_settings, _token(session_settings, admin, tenant))
    try:
        # Attempt to mutate object field via module path must 404
        denied = client.patch(
            f"/api/admin/crm/modules/CUSTOMERS/fields/{field['id']}",
            json={"label": "Hacked"},
        )
        assert denied.status_code == 404
        _ = obj
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_cross_tenant_relationship_link_fails(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    _seed(session, tenant)
    OrganizationService(session).update(
        tenant_b.id,
        actor="b",
        name="Other",
        industry="ecommerce",
        business_type="products",
    )
    CrmSetupService(session).setup(tenant_b.id, actor="b")

    objs_a = CustomObjectService(session)
    equipment = objs_a.create_definition(
        tenant.id, object_key="equip", name="Equip", actor="a"
    )
    eq_id = uuid.UUID(equipment["id"])
    rec_a = objs_a.create_record(tenant.id, eq_id, actor="a", values={})

    objs_b = CustomObjectService(session)
    equipment_b = objs_b.create_definition(
        tenant_b.id, object_key="equip", name="Equip", actor="b"
    )
    rec_b = objs_b.create_record(
        tenant_b.id, uuid.UUID(equipment_b["id"]), actor="b", values={}
    )

    customer = Customer(tenant_id=tenant.id, name="A", email="a@t.test")
    session.add(customer)
    session.flush()

    RelationshipService(session).create_definition(
        tenant.id,
        relationship_key="customer_equip",
        source_type="module",
        source_key="CUSTOMERS",
        target_type="object",
        target_key="equip",
        cardinality="ONE_TO_MANY",
        actor="a",
    )
    with pytest.raises(DynamicCrmError):
        RelationshipService(session).link(
            tenant.id,
            relationship_key="customer_equip",
            source_record_id=customer.id,
            target_record_id=uuid.UUID(rec_b["id"]),
            actor="a",
        )
    # Valid same-tenant link still works
    RelationshipService(session).link(
        tenant.id,
        relationship_key="customer_equip",
        source_record_id=customer.id,
        target_record_id=uuid.UUID(rec_a["id"]),
        actor="a",
    )


def test_admin_has_crm_configure_permission(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    _seed(session, tenant)
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="harden-admin@t.test",
        password="password123",
        name="Admin",
    )
    client = _client(session, session_settings, _token(session_settings, admin, tenant))
    try:
        res = client.patch("/api/admin/crm/modules/JOBS", json={"enabled": False})
        assert res.status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
