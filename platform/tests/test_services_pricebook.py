"""Phase 7 Services & Pricebook: CRUD, pricing resolution, isolation, RBAC."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.crm.services import ServicesPricebookService
from callbot_platform.crm.services.constants import (
    PRICE_SOURCE_NO_PRICE,
    PRICE_SOURCE_OVERRIDE,
    PRICE_SOURCE_PRICEBOOK_ITEM,
    PRICE_SOURCE_SERVICE_BASE,
)
from callbot_platform.db.models import Tenant


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _svc(session: Session) -> ServicesPricebookService:
    return ServicesPricebookService(session)


def test_service_crud_search_archive(session: Session, tenant: Tenant) -> None:
    api = _svc(session)
    cat = api.categories.create(tenant.id, name="HVAC", actor="t")
    child = api.categories.create(
        tenant.id, name="Repair", parent_id=uuid.UUID(cat["id"]), actor="t"
    )
    created = api.create_service(
        tenant.id,
        name="AC Tune-Up",
        code="ac-tune",
        category_id=uuid.UUID(child["id"]),
        duration_minutes=60,
        base_price="100.00",
        cost="40",
        pricing_type="FIXED",
        actor="t",
    )
    assert created["code"] == "ac-tune"
    assert Decimal(created["base_price"]) == Decimal("100.0000")

    with pytest.raises(CrmError) as dup:
        api.create_service(tenant.id, name="Other", code="AC-TUNE", actor="t")
    assert dup.value.code == "code_conflict"

    found = api.list_services(tenant.id, q="water")
    assert found["services"] == []
    found = api.list_services(tenant.id, q="tune")
    assert len(found["services"]) == 1
    found = api.list_services(
        tenant.id, category_id=uuid.UUID(child["id"]), min_price="50"
    )
    assert len(found["services"]) == 1

    archived = api.archive_service(tenant.id, uuid.UUID(created["id"]), actor="t")
    assert archived["archived_at"] is not None
    active = api.list_services(tenant.id)
    assert active["services"] == []
    restored = api.restore_service(tenant.id, uuid.UUID(created["id"]), actor="t")
    assert restored["archived_at"] is None


def test_category_tree_cycle_and_isolation(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    api = _svc(session)
    root = api.categories.create(tenant.id, name="Plumbing", actor="t")
    child = api.categories.create(
        tenant.id, name="Emergency", parent_id=uuid.UUID(root["id"]), actor="t"
    )
    tree = api.categories.tree(tenant.id)
    assert len(tree) == 1
    assert tree[0]["children"][0]["name"] == "Emergency"

    with pytest.raises(CrmError) as cycle:
        api.categories.update(
            tenant.id,
            uuid.UUID(root["id"]),
            parent_id=uuid.UUID(child["id"]),
            actor="t",
        )
    assert cycle.value.code == "category_cycle"

    with pytest.raises(CrmError) as self_parent:
        api.categories.update(
            tenant.id,
            uuid.UUID(root["id"]),
            parent_id=uuid.UUID(root["id"]),
            actor="t",
        )
    assert self_parent.value.code == "invalid_parent"

    other = api.categories.create(tenant_b.id, name="Plumbing", actor="t")
    with pytest.raises(CrmError):
        api.categories.update(
            tenant.id,
            uuid.UUID(root["id"]),
            parent_id=uuid.UUID(other["id"]),
            actor="t",
        )
    assert api.categories.tree(tenant_b.id)[0]["id"] == other["id"]


def test_pricebook_pricing_types_and_resolution(
    session: Session, tenant: Tenant
) -> None:
    api = _svc(session)
    svc = api.create_service(
        tenant.id,
        name="Drain Cleaning",
        code="DRAIN",
        base_price="100",
        pricing_type="FIXED",
        actor="t",
    )
    pb = api.pricebooks.create(tenant.id, name="Standard", is_default=True, actor="t")
    item = api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="120",
        actor="t",
    )
    assert item["price"] == "120.0000"

    resolved = api.resolve_price(
        tenant.id, service_id=uuid.UUID(svc["id"]), pricebook_id=uuid.UUID(pb["id"])
    )
    assert resolved["source"] == PRICE_SOURCE_PRICEBOOK_ITEM
    assert Decimal(resolved["price"]) == Decimal("120.0000")

    ov = api.pricebooks.create_override(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        override_price="110",
        actor="t",
    )
    resolved = api.resolve_price(
        tenant.id, service_id=uuid.UUID(svc["id"]), pricebook_id=uuid.UUID(pb["id"])
    )
    assert resolved["source"] == PRICE_SOURCE_OVERRIDE
    assert Decimal(resolved["price"]) == Decimal("110.0000")
    assert resolved["override_id"] == ov["id"]

    # Expire override → pricebook item
    past = datetime.now(UTC) - timedelta(days=2)
    mid = datetime.now(UTC) - timedelta(days=1)
    api.pricebooks.archive_override(
        tenant.id, uuid.UUID(pb["id"]), uuid.UUID(ov["id"]), actor="t"
    )
    api.pricebooks.create_override(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        override_price="95",
        effective_from=past,
        effective_until=mid,
        actor="t",
    )
    resolved = api.resolve_price(
        tenant.id, service_id=uuid.UUID(svc["id"]), pricebook_id=uuid.UUID(pb["id"])
    )
    assert resolved["source"] == PRICE_SOURCE_PRICEBOOK_ITEM
    assert Decimal(resolved["price"]) == Decimal("120.0000")

    # Expire item → service base
    api.pricebooks.archive_item(
        tenant.id, uuid.UUID(pb["id"]), uuid.UUID(item["id"]), actor="t"
    )
    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="120",
        effective_from=past,
        effective_until=mid,
        actor="t",
    )
    resolved = api.resolve_price(
        tenant.id, service_id=uuid.UUID(svc["id"]), pricebook_id=uuid.UUID(pb["id"])
    )
    assert resolved["source"] == PRICE_SOURCE_SERVICE_BASE
    assert Decimal(resolved["price"]) == Decimal("100.0000")


def test_pricing_types_hourly_starting_quote(session: Session, tenant: Tenant) -> None:
    api = _svc(session)
    labor = api.create_service(
        tenant.id, name="Labor", code="LAB", base_price="80", actor="t"
    )
    start = api.create_service(
        tenant.id, name="Drain", code="DRN", base_price="50", actor="t"
    )
    quote = api.create_service(
        tenant.id,
        name="Commercial Install",
        code="CI",
        pricing_type="CUSTOM_QUOTE",
        actor="t",
    )
    pb = api.pricebooks.create(tenant.id, name="Rates", is_default=True, actor="t")
    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(labor["id"]),
        pricing_type="HOURLY",
        hourly_rate="125",
        actor="t",
    )
    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(start["id"]),
        pricing_type="STARTING_AT",
        starting_price="99",
        actor="t",
    )
    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(quote["id"]),
        pricing_type="CUSTOM_QUOTE",
        actor="t",
    )
    r1 = api.resolve_price(tenant.id, service_id=uuid.UUID(labor["id"]))
    assert r1["pricing_type"] == "HOURLY"
    assert Decimal(r1["price"]) == Decimal("125.0000")
    r2 = api.resolve_price(tenant.id, service_id=uuid.UUID(start["id"]))
    assert r2["pricing_type"] == "STARTING_AT"
    assert Decimal(r2["price"]) == Decimal("99.0000")
    r3 = api.resolve_price(tenant.id, service_id=uuid.UUID(quote["id"]))
    assert r3["pricing_type"] == "CUSTOM_QUOTE"
    assert r3["price"] is None


def test_labor_material_components(session: Session, tenant: Tenant) -> None:
    api = _svc(session)
    catalog = ProductCatalogService(session)
    prod = catalog.create(
        tenant.id, name="Copper Pipe", sku="CU-1", price="10", actor="t"
    )
    variant = catalog.variants.create(
        tenant.id, uuid.UUID(prod["id"]), sku="CU-1-1IN", actor="t"
    )
    svc = api.create_service(
        tenant.id, name="Install", code="INST", base_price="500", actor="t"
    )
    pb = api.pricebooks.create(tenant.id, name="Jobs", actor="t")
    item = api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="900",
        components=[
            {
                "component_type": "LABOR",
                "name": "Install labor",
                "quantity": "4",
                "unit_price": "125",
            },
            {
                "component_type": "MATERIAL",
                "product_variant_id": variant["id"],
                "quantity": "10",
                "unit_price": "12",
            },
        ],
        actor="t",
    )
    assert len(item["components"]) == 2
    material = next(c for c in item["components"] if c["component_type"] == "MATERIAL")
    assert material["variant_sku"] == "CU-1-1IN"
    assert Decimal(material["line_total"]) == Decimal("120.0000")

    api.pricebooks.archive_item(
        tenant.id, uuid.UUID(pb["id"]), uuid.UUID(item["id"]), actor="t"
    )

    # Cross-tenant variant rejected
    other = Tenant(name="X", slug=f"x-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    foreign = catalog.create(other.id, name="Pipe", sku="P-1", price="1", actor="t")
    fvar = catalog.variants.create(
        other.id, uuid.UUID(foreign["id"]), sku="P-1-A", actor="t"
    )
    with pytest.raises(CrmError) as exc:
        api.pricebooks.create_item(
            tenant.id,
            uuid.UUID(pb["id"]),
            service_id=uuid.UUID(svc["id"]),
            pricing_type="FIXED",
            price="1",
            components=[
                {
                    "component_type": "MATERIAL",
                    "product_variant_id": fvar["id"],
                    "quantity": "1",
                }
            ],
            actor="t",
        )
    assert exc.value.code == "invalid_variant"


def test_tenant_isolation_idor(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    api = _svc(session)
    a = api.create_service(
        tenant.id, name="A Service", code="A1", base_price="10", actor="t"
    )
    pb = api.pricebooks.create(tenant.id, name="PB-A", actor="t")
    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(a["id"]),
        pricing_type="FIXED",
        price="15",
        actor="t",
    )

    with pytest.raises(CrmError) as nf:
        api.get_service(tenant_b.id, uuid.UUID(a["id"]))
    assert nf.value.code == "not_found"

    with pytest.raises(CrmError):
        api.pricebooks.get(tenant_b.id, uuid.UUID(pb["id"]))

    b_svc = api.create_service(tenant_b.id, name="B", code="B1", actor="t")
    with pytest.raises(CrmError) as bad_ref:
        api.pricebooks.create_item(
            tenant.id,
            uuid.UUID(pb["id"]),
            service_id=uuid.UUID(b_svc["id"]),
            pricing_type="FIXED",
            price="1",
            actor="t",
        )
    assert bad_ref.value.code == "invalid_service"

    with pytest.raises(CrmError):
        api.resolve_price(
            tenant_b.id,
            service_id=uuid.UUID(a["id"]),
            pricebook_id=uuid.UUID(pb["id"]),
        )


def test_overlap_prevention_and_default_pricebook(
    session: Session, tenant: Tenant
) -> None:
    api = _svc(session)
    svc = api.create_service(tenant.id, name="S", code="S1", base_price="10", actor="t")
    pb1 = api.pricebooks.create(tenant.id, name="Std", is_default=True, actor="t")
    pb2 = api.pricebooks.create(tenant.id, name="VIP", is_default=True, actor="t")
    refreshed = api.pricebooks.get(tenant.id, uuid.UUID(pb1["id"]))
    assert refreshed["is_default"] is False
    assert api.pricebooks.get(tenant.id, uuid.UUID(pb2["id"]))["is_default"] is True

    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb2["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="20",
        actor="t",
    )
    with pytest.raises(CrmError) as ov:
        api.pricebooks.create_item(
            tenant.id,
            uuid.UUID(pb2["id"]),
            service_id=uuid.UUID(svc["id"]),
            pricing_type="FIXED",
            price="25",
            actor="t",
        )
    assert ov.value.code == "effective_overlap"


def test_no_price_fallback(session: Session, tenant: Tenant) -> None:
    api = _svc(session)
    svc = api.create_service(
        tenant.id,
        name="Custom Only",
        code="CO",
        pricing_type="CUSTOM_QUOTE",
        actor="t",
    )
    resolved = api.resolve_price(tenant.id, service_id=uuid.UUID(svc["id"]))
    assert resolved["source"] == PRICE_SOURCE_NO_PRICE
    assert resolved["price"] is None


def test_negative_money_rejected(session: Session, tenant: Tenant) -> None:
    api = _svc(session)
    with pytest.raises(CrmError):
        api.create_service(tenant.id, name="Bad", base_price="-1", actor="t")
    with pytest.raises(CrmError):
        api.create_service(tenant.id, name="Bad2", duration_minutes=0, actor="t")


def test_pagination_bounded(session: Session, tenant: Tenant) -> None:
    api = _svc(session)
    for i in range(5):
        api.create_service(
            tenant.id, name=f"Svc {i}", code=f"C{i}", base_price="1", actor="t"
        )
    page1 = api.list_services(tenant.id, limit=2)
    assert len(page1["services"]) == 2
    assert page1["next_cursor"]
    page2 = api.list_services(tenant.id, limit=2, cursor=page1["next_cursor"])
    assert len(page2["services"]) == 2
    ids = {s["id"] for s in page1["services"]} | {s["id"] for s in page2["services"]}
    assert len(ids) == 4
