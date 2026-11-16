"""Dynamic CRM Engine — modules, fields, objects, relationships."""

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
from callbot_platform.dynamic_crm import (
    CustomObjectService,
    DynamicCrmError,
    EffectiveCrmConfigurationService,
    FieldDefinitionService,
    FieldValueService,
    ModuleConfigService,
    RelationshipService,
)
from callbot_platform.main import app
from callbot_platform.organization import OrganizationService
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-dynamic-crm-ok32",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
    )


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Beta Dyn", slug=f"beta-dyn-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


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


def _seed_crm(session: Session, tenant: Tenant) -> None:
    OrganizationService(session).update(
        tenant.id,
        actor="seed",
        name="Dyn HVAC",
        industry="hvac",
        business_type="services",
    )
    CrmSetupService(session).setup(tenant.id, actor="seed")


def test_module_registry_and_enable_disable(session: Session, tenant: Tenant) -> None:
    _seed_crm(session, tenant)
    svc = ModuleConfigService(session)
    modules = svc.list_modules(tenant.id)
    assert any(m["key"] == "CUSTOMERS" and m["enabled"] for m in modules)
    jobs = svc.set_enabled(tenant.id, "JOBS", enabled=False, actor="a")
    assert jobs["enabled"] is False
    with pytest.raises(DynamicCrmError) as req:
        svc.set_enabled(tenant.id, "CUSTOMERS", enabled=False, actor="a")
    assert req.value.code == "module_required"
    again = svc.set_enabled(tenant.id, "JOBS", enabled=True, actor="a")
    assert again["enabled"] is True
    reordered = svc.reorder(tenant.id, ["JOBS", "CUSTOMERS", "CALLS"], actor="a")
    order = {m["key"]: m["display_order"] for m in reordered}
    assert order["JOBS"] < order["CUSTOMERS"]


def test_effective_configuration_navigation(session: Session, tenant: Tenant) -> None:
    _seed_crm(session, tenant)
    ModuleConfigService(session).set_enabled(
        tenant.id, "JOBS", enabled=False, actor="a"
    )
    cfg = EffectiveCrmConfigurationService(session).get(tenant.id)
    keys = {n["key"] for n in cfg["navigation"]}
    assert "CUSTOMERS" in keys
    assert "JOBS" not in keys
    assert "PROPERTIES" not in keys
    assert "PAYMENTS" not in keys
    customers = next(m for m in cfg["modules"] if m["key"] == "CUSTOMERS")
    assert customers["ui_live"] is True
    properties = next(m for m in cfg["modules"] if m["key"] == "PROPERTIES")
    assert properties["ui_live"] is False


def test_stub_module_cannot_be_enabled(session: Session, tenant: Tenant) -> None:
    _seed_crm(session, tenant)
    svc = ModuleConfigService(session)
    with pytest.raises(DynamicCrmError) as exc:
        svc.set_enabled(tenant.id, "PROPERTIES", enabled=True, actor="a")
    assert exc.value.code == "module_not_available"
    enabled = {m["key"] for m in svc.list_modules(tenant.id) if m["enabled"]}
    assert "PROPERTIES" not in enabled
    assert "PAYMENTS" not in enabled


def test_custom_fields_validation_and_values(session: Session, tenant: Tenant) -> None:
    _seed_crm(session, tenant)
    fields = FieldDefinitionService(session)
    field = fields.create_field(
        tenant.id,
        owner_scope="module",
        owner_key="CUSTOMERS",
        field_key="priority",
        label="Priority",
        field_type="DROPDOWN",
        actor="a",
        required=True,
        configuration={"options": ["low", "high"]},
        default_value="low",
    )
    assert field["field_type"] == "DROPDOWN"
    record_id = uuid.uuid4()
    values = FieldValueService(session)
    saved = values.set_values(
        tenant.id,
        record_type="module",
        record_id=record_id,
        owner_scope="module",
        owner_key="CUSTOMERS",
        values={},
        apply_defaults=True,
        is_create=True,
    )
    assert saved["priority"] == "low"
    with pytest.raises(DynamicCrmError):
        values.set_values(
            tenant.id,
            record_type="module",
            record_id=uuid.uuid4(),
            owner_scope="module",
            owner_key="CUSTOMERS",
            values={"priority": "urgent"},
            is_create=True,
        )
    values.set_values(
        tenant.id,
        record_type="module",
        record_id=record_id,
        owner_scope="module",
        owner_key="CUSTOMERS",
        values={"priority": "high"},
        is_create=False,
    )
    found = values.find_record_ids(
        tenant.id,
        owner_scope="module",
        owner_key="CUSTOMERS",
        filters=[{"field": "priority", "operator": "equals", "value": "high"}],
    )
    assert record_id in found


def test_custom_objects_and_search(session: Session, tenant: Tenant) -> None:
    _seed_crm(session, tenant)
    objs = CustomObjectService(session)
    definition = objs.create_definition(
        tenant.id, object_key="vehicle", name="Vehicle", actor="a"
    )
    FieldDefinitionService(session).create_field(
        tenant.id,
        owner_scope="object",
        owner_key="vehicle",
        field_key="vin",
        label="VIN",
        field_type="TEXT",
        actor="a",
        required=True,
    )
    FieldDefinitionService(session).create_field(
        tenant.id,
        owner_scope="object",
        owner_key="vehicle",
        field_key="year",
        label="Year",
        field_type="NUMBER",
        actor="a",
    )
    record = objs.create_record(
        tenant.id,
        uuid.UUID(definition["id"]),
        actor="a",
        values={"vin": "ABC123", "year": 2020},
    )
    assert record["values"]["vin"] == "ABC123"
    listed = objs.list_records(
        tenant.id,
        uuid.UUID(definition["id"]),
        filters=[{"field": "vin", "operator": "equals", "value": "ABC123"}],
    )
    assert listed["total"] >= 1
    objs.archive_record(
        tenant.id, uuid.UUID(definition["id"]), uuid.UUID(record["id"]), actor="a"
    )
    archived = objs.get_record(
        tenant.id, uuid.UUID(definition["id"]), uuid.UUID(record["id"])
    )
    assert archived["archived_at"] is not None


def test_relationships_cardinality_and_isolation(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    _seed_crm(session, tenant)
    OrganizationService(session).update(
        tenant_b.id,
        actor="b",
        name="Other",
        industry="ecommerce",
        business_type="products",
    )
    CrmSetupService(session).setup(tenant_b.id, actor="b")

    objs = CustomObjectService(session)
    equipment = objs.create_definition(
        tenant.id, object_key="equipment_unit", name="Equipment", actor="a"
    )
    eq_id = uuid.UUID(equipment["id"])
    r1 = objs.create_record(tenant.id, eq_id, actor="a", values={})
    r2 = objs.create_record(tenant.id, eq_id, actor="a", values={})

    rels = RelationshipService(session)
    rel = rels.create_definition(
        tenant.id,
        relationship_key="customer_equipment",
        source_type="module",
        source_key="CUSTOMERS",
        target_type="object",
        target_key="equipment_unit",
        cardinality="ONE_TO_MANY",
        actor="a",
        label="Equipment",
    )
    assert rel["cardinality"] == "ONE_TO_MANY"

    # Use synthetic customer UUID accepted for modules without strong FK when
    # customer row missing — create a real customer for integrity.
    from callbot_platform.db.models.crm import Customer

    customer = Customer(
        tenant_id=tenant.id,
        name="Pat",
        email="pat@example.com",
    )
    session.add(customer)
    session.flush()

    link = rels.link(
        tenant.id,
        relationship_key="customer_equipment",
        source_record_id=customer.id,
        target_record_id=uuid.UUID(r1["id"]),
        actor="a",
    )
    assert link["target_record_id"] == r1["id"]
    customer2 = Customer(
        tenant_id=tenant.id,
        name="Other",
        email="other@example.com",
    )
    session.add(customer2)
    session.flush()
    with pytest.raises(DynamicCrmError) as card:
        rels.link(
            tenant.id,
            relationship_key="customer_equipment",
            source_record_id=customer2.id,
            target_record_id=uuid.UUID(r1["id"]),
            actor="a",
        )
    assert card.value.code == "cardinality_violation"

    # Tenant B cannot see tenant A definition via service scope
    b_defs = RelationshipService(session).list_definitions(tenant_b.id)
    assert all(d["relationship_key"] != "customer_equipment" for d in b_defs)

    # M2M
    rels.create_definition(
        tenant.id,
        relationship_key="equipment_pairs",
        source_type="object",
        source_key="equipment_unit",
        target_type="object",
        target_key="equipment_unit",
        cardinality="MANY_TO_MANY",
        actor="a",
    )
    rels.link(
        tenant.id,
        relationship_key="equipment_pairs",
        source_record_id=uuid.UUID(r1["id"]),
        target_record_id=uuid.UUID(r2["id"]),
        actor="a",
    )


def test_api_rbac_and_idor(
    session: Session, tenant: Tenant, tenant_b: Tenant, session_settings: Settings
) -> None:
    _seed_crm(session, tenant)
    admin_a = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="dyn-a@t.test",
        password="password123",
        name="A",
    )
    admin_b = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant_b.id,
        email="dyn-b@t.test",
        password="password123",
        name="B",
    )
    dispatcher = AuthRepository(session).create_user(
        tenant.id,
        email="dyn-disp@t.test",
        password="password123",
        name="Disp",
        role="dispatcher",
    )
    obj = CustomObjectService(session).create_definition(
        tenant.id, object_key="asset", name="Asset", actor="a"
    )

    client = _client(
        session, session_settings, _token(session_settings, admin_a, tenant)
    )
    try:
        got = client.get("/api/admin/crm/configuration")
        assert got.status_code == 200
        assert "navigation" in got.json()["configuration"]

        patched = client.patch("/api/admin/crm/modules/JOBS", json={"enabled": False})
        assert patched.status_code == 200
        assert patched.json()["module"]["enabled"] is False

        client.cookies.set(
            session_settings.session_cookie_name,
            _token(session_settings, dispatcher, tenant),
        )
        denied = client.patch("/api/admin/crm/modules/JOBS", json={"enabled": True})
        assert denied.status_code == 403

        client.cookies.set(
            session_settings.session_cookie_name,
            _token(session_settings, admin_b, tenant_b),
        )
        # IDOR: tenant B cannot read tenant A's object records
        idor = client.get(f"/api/admin/crm/objects/{obj['id']}/records")
        assert idor.status_code in {403, 404}
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
