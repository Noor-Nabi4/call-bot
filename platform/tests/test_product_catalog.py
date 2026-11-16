"""Phase 5 Product Catalog: products, categories, variants, images, isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Tenant
from callbot_platform.storage.base import ALLOWED_PRODUCT_IMAGE_MIME_TYPES


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def test_product_crud_sku_money_and_search(session: Session, tenant: Tenant) -> None:
    svc = ProductCatalogService(session)
    created = svc.create(
        tenant.id,
        name="Widget Pro",
        sku="wdg-001",
        price="19.9900",
        cost="8.5",
        tax_rate="8.25",
        weight="1.5",
        weight_unit="kg",
        brand="Acme Tools",
        actor="tester",
        include_cost=True,
    )
    assert created["sku"] == "wdg-001"
    assert created["price"] == "19.9900"
    assert created["cost"] == "8.5000"
    assert created["tax_rate"] == "8.2500"
    assert created["weight_unit"] == "KG"
    assert created["brand"]["name"] == "Acme Tools"

    with pytest.raises(CrmError) as exc:
        svc.create(tenant.id, name="Dup", sku="WDG-001", actor="tester")
    assert exc.value.code == "sku_conflict"

    pid = uuid.UUID(created["id"])
    updated = svc.update(
        tenant.id, pid, actor="tester", price="21.00", include_cost=True
    )
    assert updated["price"] == "21.0000"

    found = svc.search(tenant.id, q="WDG-001")
    assert [p["id"] for p in found["products"]] == [created["id"]]

    svc.archive(tenant.id, pid, actor="tester")
    listed = svc.list(tenant.id)
    assert all(p["id"] != created["id"] for p in listed["products"])
    svc.restore(tenant.id, pid, actor="tester")
    listed2 = svc.list(tenant.id)
    assert any(p["id"] == created["id"] for p in listed2["products"])


def test_categories_hierarchy_and_cycle(session: Session, tenant: Tenant) -> None:
    svc = ProductCatalogService(session)
    root = svc.categories.create(tenant.id, name="Clothing", actor="t")
    men = svc.categories.create(
        tenant.id, name="Men", parent_id=uuid.UUID(root["id"]), actor="t"
    )
    shirts = svc.categories.create(
        tenant.id, name="Shirts", parent_id=uuid.UUID(men["id"]), actor="t"
    )
    # Cycle: move Clothing under Shirts
    with pytest.raises(CrmError) as exc:
        svc.categories.update(
            tenant.id,
            uuid.UUID(root["id"]),
            actor="t",
            parent_id=uuid.UUID(shirts["id"]),
        )
    assert exc.value.code == "category_cycle"

    with pytest.raises(CrmError):
        svc.categories.update(
            tenant.id, uuid.UUID(root["id"]), actor="t", parent_id=uuid.UUID(root["id"])
        )

    tree = svc.categories.tree(tenant.id)
    assert any(n["name"] == "Clothing" for n in tree)

    prod = svc.create(
        tenant.id,
        name="Tee",
        sku="TEE-1",
        category_id=uuid.UUID(shirts["id"]),
        actor="t",
    )
    with pytest.raises(CrmError) as exc2:
        svc.categories.archive(tenant.id, uuid.UUID(shirts["id"]), actor="t")
    assert exc2.value.code == "category_in_use"

    svc.categories.archive(
        tenant.id,
        uuid.UUID(shirts["id"]),
        actor="t",
        reassign_products=True,
        reassign_to_category_id=uuid.UUID(men["id"]),
    )
    got = svc.get(tenant.id, uuid.UUID(prod["id"]))
    assert got["category_id"] == men["id"]


def test_variants_attributes_fingerprint_and_price_override(
    session: Session, tenant: Tenant
) -> None:
    svc = ProductCatalogService(session)
    prod = svc.create(tenant.id, name="T-Shirt", sku="TS", price="20.00", actor="t")
    pid = uuid.UUID(prod["id"])
    color = svc.upsert_attribute(
        tenant.id, pid, name="Color", values=["Black", "Blue"], actor="t"
    )
    size = svc.upsert_attribute(
        tenant.id, pid, name="Size", values=["S", "M"], actor="t"
    )
    black = next(v for v in color["values"] if v["value"] == "Black")
    small = next(v for v in size["values"] if v["value"] == "S")
    medium = next(v for v in size["values"] if v["value"] == "M")

    v1 = svc.variants.create(
        tenant.id,
        pid,
        sku="TS-BLK-S",
        attribute_value_ids=[uuid.UUID(black["id"]), uuid.UUID(small["id"])],
        price="22.00",
        stock_on_hand=5,
        actor="t",
        include_cost=True,
    )
    assert v1["effective_price"] == "22.0000"
    assert v1["stock_on_hand"] == 5

    with pytest.raises(CrmError) as exc:
        svc.variants.create(
            tenant.id,
            pid,
            sku="TS-BLK-S-DUP",
            attribute_value_ids=[uuid.UUID(small["id"]), uuid.UUID(black["id"])],
            actor="t",
        )
    assert exc.value.code == "variant_conflict"

    v2 = svc.variants.create(
        tenant.id,
        pid,
        sku="TS-BLK-M",
        attribute_value_ids=[uuid.UUID(black["id"]), uuid.UUID(medium["id"])],
        actor="t",
    )
    assert v2["effective_price"] == "20.0000"  # inherits product price


def test_images_primary_and_mime(session: Session, tenant: Tenant) -> None:
    assert "image/png" in ALLOWED_PRODUCT_IMAGE_MIME_TYPES
    svc = ProductCatalogService(session)
    prod = svc.create(tenant.id, name="Img Prod", sku="IMG-1", actor="t")
    pid = uuid.UUID(prod["id"])
    # Minimal PNG (1x1)
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
        b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img1 = svc.images.upload(
        tenant.id, pid, data=png, content_type="image/png", actor="t", is_primary=True
    )
    assert img1["is_primary"] is True
    img2 = svc.images.upload(
        tenant.id, pid, data=png, content_type="image/png", actor="t", is_primary=True
    )
    assert img2["is_primary"] is True
    listed = svc.images.list(tenant.id, pid)
    primaries = [i for i in listed if i["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["id"] == img2["id"]

    with pytest.raises(CrmError) as exc:
        svc.images.upload(
            tenant.id, pid, data=b"not-an-image", content_type="image/png", actor="t"
        )
    assert exc.value.code in {"unsupported_image_type", "invalid_image"}


def test_tenant_isolation_idor(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    svc = ProductCatalogService(session)
    a = svc.create(tenant.id, name="A Prod", sku="A-1", actor="t")
    b = svc.create(tenant_b.id, name="B Prod", sku="B-1", actor="t")
    a_id = uuid.UUID(a["id"])
    b_id = uuid.UUID(b["id"])
    cat_a = svc.categories.create(tenant.id, name="A Cat", actor="t")

    assert all(
        p["id"] != b["id"] for p in svc.search(tenant.id, q="B Prod")["products"]
    )

    with pytest.raises(CrmError):
        svc.get(tenant.id, b_id)
    with pytest.raises(CrmError):
        svc.update(tenant.id, b_id, name="Hacked")
    with pytest.raises(CrmError):
        svc.archive(tenant.id, b_id)
    with pytest.raises(CrmError):
        svc.variants.create(tenant.id, b_id, sku="X", attribute_value_ids=[], actor="t")

    # Same-tenant category assignment is allowed
    ok = svc.create(
        tenant.id,
        name="Good Cat",
        sku="GOOD-CAT",
        category_id=uuid.UUID(cat_a["id"]),
        actor="t",
    )
    assert ok["category_id"] == cat_a["id"]

    # Cross-tenant category assignment must fail
    with pytest.raises(CrmError):
        svc.create(
            tenant_b.id,
            name="Steal Cat",
            sku="STEAL-1",
            category_id=uuid.UUID(cat_a["id"]),
            actor="t",
        )
    with pytest.raises(CrmError):
        svc.images.list(tenant.id, b_id)
    with pytest.raises(CrmError):
        svc.categories.get(tenant_b.id, uuid.UUID(cat_a["id"]))

    assert a_id != b_id


def test_price_rejects_negative(session: Session, tenant: Tenant) -> None:
    svc = ProductCatalogService(session)
    with pytest.raises(CrmError) as exc:
        svc.create(tenant.id, name="Bad", price="-1", actor="t")
    assert exc.value.code == "invalid_price"
    with pytest.raises(CrmError):
        svc.create(tenant.id, name="BadTax", tax_rate="101", actor="t")


def test_archive_releases_variant_skus(session: Session, tenant: Tenant) -> None:
    svc = ProductCatalogService(session)
    prod = svc.create(tenant.id, name="Hoodie", sku="HD-BASE", price="40", actor="t")
    pid = uuid.UUID(prod["id"])
    color = svc.upsert_attribute(
        tenant.id, pid, name="Color", values=["Red"], actor="t"
    )
    red = color["values"][0]
    variant = svc.variants.create(
        tenant.id,
        pid,
        sku="HD-RED",
        attribute_value_ids=[uuid.UUID(red["id"])],
        actor="t",
    )
    assert variant["sku"] == "HD-RED"

    svc.archive(tenant.id, pid, actor="t")
    # Variant SKU must be reusable after cascading product archive.
    other = svc.create(tenant.id, name="Other", sku="HD-RED", actor="t")
    assert other["sku"] == "HD-RED"

    with pytest.raises(CrmError) as exc:
        svc.restore(tenant.id, pid, actor="t")
    assert exc.value.code == "sku_conflict"


def test_has_variants_ignores_archived(session: Session, tenant: Tenant) -> None:
    svc = ProductCatalogService(session)
    prod = svc.create(tenant.id, name="Cap", sku="CAP-1", actor="t")
    pid = uuid.UUID(prod["id"])
    color = svc.upsert_attribute(
        tenant.id, pid, name="Color", values=["Navy"], actor="t"
    )
    navy = color["values"][0]
    variant = svc.variants.create(
        tenant.id,
        pid,
        sku="CAP-NAVY",
        attribute_value_ids=[uuid.UUID(navy["id"])],
        actor="t",
    )
    got = svc.get(tenant.id, pid)
    assert got["has_variants"] is True

    svc.variants.archive(tenant.id, pid, uuid.UUID(variant["id"]), actor="t")
    got2 = svc.get(tenant.id, pid)
    assert got2["has_variants"] is False
    assert got2["variants"] == []
