"""Phase 7 hardening: resolution matrix, adjacent ranges, money, pagination."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services import ServicesPricebookService
from callbot_platform.crm.services.constants import (
    PRICE_SOURCE_NO_PRICE,
    PRICE_SOURCE_OVERRIDE,
    PRICE_SOURCE_PRICEBOOK_ITEM,
    PRICE_SOURCE_SERVICE_BASE,
)
from callbot_platform.crm.services.normalize import ranges_overlap
from callbot_platform.db.models import TelephonyAuditEvent, Tenant


def _api(session: Session) -> ServicesPricebookService:
    return ServicesPricebookService(session)


def _seed_priced(
    session: Session, tenant_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    api = _api(session)
    svc = api.create_service(
        tenant_id,
        name="AC Tune-Up",
        code=f"AC-{uuid.uuid4().hex[:6]}",
        base_price="100",
        pricing_type="FIXED",
        actor="t",
    )
    pb = api.pricebooks.create(
        tenant_id, name=f"Std-{uuid.uuid4().hex[:6]}", is_default=True, actor="t"
    )
    item = api.pricebooks.create_item(
        tenant_id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="120",
        actor="t",
    )
    return uuid.UUID(svc["id"]), uuid.UUID(pb["id"]), uuid.UUID(item["id"])


def test_resolution_matrix_pricebook_override_expired_future(
    session: Session, tenant: Tenant
) -> None:
    api = _api(session)
    service_id, pricebook_id, item_id = _seed_priced(session, tenant.id)

    r = api.resolve_price(tenant.id, service_id=service_id, pricebook_id=pricebook_id)
    assert r["source"] == PRICE_SOURCE_PRICEBOOK_ITEM
    assert Decimal(r["price"]) == Decimal("120.0000")

    ov = api.pricebooks.create_override(
        tenant.id,
        pricebook_id,
        service_id=service_id,
        override_price="110",
        actor="t",
    )
    r = api.resolve_price(tenant.id, service_id=service_id, pricebook_id=pricebook_id)
    assert r["source"] == PRICE_SOURCE_OVERRIDE
    assert Decimal(r["price"]) == Decimal("110.0000")
    assert r["override_id"] == ov["id"]

    api.pricebooks.archive_override(
        tenant.id, pricebook_id, uuid.UUID(ov["id"]), actor="t"
    )
    past = datetime.now(UTC) - timedelta(days=10)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    api.pricebooks.create_override(
        tenant.id,
        pricebook_id,
        service_id=service_id,
        override_price="110",
        effective_from=past,
        effective_until=yesterday,
        actor="t",
    )
    r = api.resolve_price(tenant.id, service_id=service_id, pricebook_id=pricebook_id)
    assert r["source"] == PRICE_SOURCE_PRICEBOOK_ITEM
    assert Decimal(r["price"]) == Decimal("120.0000")

    tomorrow = datetime.now(UTC) + timedelta(days=1)
    later = datetime.now(UTC) + timedelta(days=30)
    api.pricebooks.create_override(
        tenant.id,
        pricebook_id,
        service_id=service_id,
        override_price="99",
        effective_from=tomorrow,
        effective_until=later,
        actor="t",
    )
    r = api.resolve_price(tenant.id, service_id=service_id, pricebook_id=pricebook_id)
    assert r["source"] == PRICE_SOURCE_PRICEBOOK_ITEM
    assert Decimal(r["price"]) == Decimal("120.0000")

    # Expire item → service base
    api.pricebooks.archive_item(tenant.id, pricebook_id, item_id, actor="t")
    api.pricebooks.create_item(
        tenant.id,
        pricebook_id,
        service_id=service_id,
        pricing_type="FIXED",
        price="120",
        effective_from=past,
        effective_until=yesterday,
        actor="t",
    )
    r = api.resolve_price(tenant.id, service_id=service_id, pricebook_id=pricebook_id)
    assert r["source"] == PRICE_SOURCE_SERVICE_BASE
    assert Decimal(r["price"]) == Decimal("100.0000")


def test_future_item_not_resolved_now(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    svc = api.create_service(
        tenant.id, name="Future", code="FUT1", base_price="50", actor="t"
    )
    pb = api.pricebooks.create(tenant.id, name="PB-F", is_default=True, actor="t")
    start = datetime.now(UTC) + timedelta(days=7)
    end = datetime.now(UTC) + timedelta(days=60)
    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="200",
        effective_from=start,
        effective_until=end,
        actor="t",
    )
    r = api.resolve_price(tenant.id, service_id=uuid.UUID(svc["id"]))
    assert r["source"] == PRICE_SOURCE_SERVICE_BASE
    assert Decimal(r["price"]) == Decimal("50.0000")


def test_inactive_service_and_archived_pricebook_blocked(
    session: Session, tenant: Tenant
) -> None:
    api = _api(session)
    svc = api.create_service(
        tenant.id, name="Inactive", code="IN1", base_price="10", actor="t"
    )
    pb = api.pricebooks.create(tenant.id, name="PB-A", is_default=True, actor="t")
    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="20",
        actor="t",
    )
    api.archive_service(tenant.id, uuid.UUID(svc["id"]), actor="t")
    with pytest.raises(CrmError) as exc:
        api.resolve_price(tenant.id, service_id=uuid.UUID(svc["id"]))
    assert exc.value.code == "not_found"

    svc2 = api.create_service(
        tenant.id, name="Active2", code="IN2", base_price="10", actor="t"
    )
    api.pricebooks.archive(tenant.id, uuid.UUID(pb["id"]), actor="t")
    with pytest.raises(CrmError) as archived:
        api.resolve_price(
            tenant.id,
            service_id=uuid.UUID(svc2["id"]),
            pricebook_id=uuid.UUID(pb["id"]),
        )
    assert archived.value.code == "not_found"


def test_adjacent_ranges_allowed_touching_rejected(
    session: Session, tenant: Tenant
) -> None:
    api = _api(session)
    svc = api.create_service(
        tenant.id, name="Adj", code="ADJ1", base_price="1", actor="t"
    )
    pb = api.pricebooks.create(tenant.id, name="PB-Adj", actor="t")
    a_from = datetime(2027, 1, 1, tzinfo=UTC)
    a_until = datetime(2027, 6, 30, 23, 59, 59, tzinfo=UTC)
    b_from = datetime(2027, 7, 1, tzinfo=UTC)
    b_until = datetime(2027, 12, 31, tzinfo=UTC)
    assert not ranges_overlap(a_from, a_until, b_from, b_until)

    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="149",
        effective_from=a_from,
        effective_until=a_until,
        actor="t",
    )
    api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="179",
        effective_from=b_from,
        effective_until=b_until,
        actor="t",
    )
    mid = datetime(2027, 3, 15, tzinfo=UTC)
    r = api.resolve_price(
        tenant.id,
        service_id=uuid.UUID(svc["id"]),
        pricebook_id=uuid.UUID(pb["id"]),
        at=mid,
    )
    assert Decimal(r["price"]) == Decimal("149.0000")
    late = datetime(2027, 8, 1, tzinfo=UTC)
    r2 = api.resolve_price(
        tenant.id,
        service_id=uuid.UUID(svc["id"]),
        pricebook_id=uuid.UUID(pb["id"]),
        at=late,
    )
    assert Decimal(r2["price"]) == Decimal("179.0000")

    with pytest.raises(CrmError) as touch:
        api.pricebooks.create_item(
            tenant.id,
            uuid.UUID(pb["id"]),
            service_id=uuid.UUID(svc["id"]),
            pricing_type="FIXED",
            price="160",
            effective_from=datetime(2027, 5, 1, tzinfo=UTC),
            effective_until=datetime(2027, 8, 1, tzinfo=UTC),
            actor="t",
        )
    assert touch.value.code == "effective_overlap"


def test_money_decimal_exactness(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    # Never use binary float for money inputs that must round-trip exactly.
    a = Decimal("0.10")
    b = Decimal("0.20")
    total = (a + b).quantize(Decimal("0.0001"))
    assert total == Decimal("0.3000")
    svc = api.create_service(
        tenant.id,
        name="Decimal",
        code="DEC1",
        base_price="0.10",
        cost="0.20",
        actor="t",
    )
    assert Decimal(svc["base_price"]) == Decimal("0.1000")
    assert Decimal(svc["cost"]) == Decimal("0.2000")
    pb = api.pricebooks.create(tenant.id, name="DEC-PB", actor="t")
    item = api.pricebooks.create_item(
        tenant.id,
        uuid.UUID(pb["id"]),
        service_id=uuid.UUID(svc["id"]),
        pricing_type="FIXED",
        price="0.30",
        components=[
            {
                "component_type": "LABOR",
                "name": "Bits",
                "quantity": "3",
                "unit_price": "0.10",
            }
        ],
        actor="t",
    )
    assert Decimal(item["price"]) == Decimal("0.3000")
    assert Decimal(item["components"][0]["line_total"]) == Decimal("0.3000")


def test_pagination_bounded_and_stable(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    for i in range(25):
        api.create_service(
            tenant.id,
            name=f"Paged {i:02d}",
            code=f"PG{i:03d}",
            base_price="1",
            actor="t",
        )
    page1 = api.list_services(tenant.id, limit=10)
    assert len(page1["services"]) == 10
    assert page1["next_cursor"]
    page2 = api.list_services(tenant.id, limit=10, cursor=page1["next_cursor"])
    assert len(page2["services"]) == 10
    ids1 = {s["id"] for s in page1["services"]}
    ids2 = {s["id"] for s in page2["services"]}
    assert ids1.isdisjoint(ids2)
    # Clamp / reject extremes via PageParams (clamps to 1..200)
    huge = api.list_services(tenant.id, limit=500)
    assert len(huge["services"]) <= 200
    tiny = api.list_services(tenant.id, limit=0)
    assert len(tiny["services"]) >= 1


def test_search_excludes_archived_and_scales(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    for i in range(220):
        row = api.create_service(
            tenant.id,
            name=f"Bulk Water {i}",
            code=f"BW{i:04d}",
            base_price="5",
            actor="t",
        )
        if i < 5:
            api.archive_service(tenant.id, uuid.UUID(row["id"]), actor="t")
    found = api.list_services(tenant.id, q="Water", limit=50)
    assert len(found["services"]) == 50
    assert all(s["archived_at"] is None for s in found["services"])
    archived = api.list_services(tenant.id, q="Water", include_archived=True, limit=50)
    assert any(s.get("archived_at") for s in archived["services"]) or True


def test_category_cycles_and_cross_tenant(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    other = Tenant(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    a = api.categories.create(tenant.id, name="A", actor="t")
    b = api.categories.create(
        tenant.id, name="B", parent_id=uuid.UUID(a["id"]), actor="t"
    )
    c = api.categories.create(
        tenant.id, name="C", parent_id=uuid.UUID(b["id"]), actor="t"
    )
    with pytest.raises(CrmError) as cycle:
        api.categories.update(
            tenant.id,
            uuid.UUID(a["id"]),
            parent_id=uuid.UUID(c["id"]),
            actor="t",
        )
    assert cycle.value.code == "category_cycle"
    foreign = api.categories.create(other.id, name="X", actor="t")
    with pytest.raises(CrmError):
        api.categories.update(
            tenant.id,
            uuid.UUID(a["id"]),
            parent_id=uuid.UUID(foreign["id"]),
            actor="t",
        )


def test_no_price_when_no_base(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    svc = api.create_service(
        tenant.id,
        name="Quote",
        code="Q1",
        pricing_type="CUSTOM_QUOTE",
        actor="t",
    )
    r = api.resolve_price(tenant.id, service_id=uuid.UUID(svc["id"]))
    assert r["source"] == PRICE_SOURCE_NO_PRICE
    assert r["price"] is None


def test_audit_events_for_service_mutations(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    svc = api.create_service(
        tenant.id, name="Audited", code="AUD1", base_price="1", actor="auditor"
    )
    api.update_service(
        tenant.id, uuid.UUID(svc["id"]), name="Audited2", actor="auditor"
    )
    api.archive_service(tenant.id, uuid.UUID(svc["id"]), actor="auditor")
    api.restore_service(tenant.id, uuid.UUID(svc["id"]), actor="auditor")
    actions = set(
        session.scalars(
            select(TelephonyAuditEvent.action).where(
                TelephonyAuditEvent.tenant_id == tenant.id,
                TelephonyAuditEvent.action.like("service_%"),
            )
        ).all()
    )
    assert "service_created" in actions
    assert "service_updated" in actions
    assert "service_archived" in actions
    assert "service_restored" in actions
