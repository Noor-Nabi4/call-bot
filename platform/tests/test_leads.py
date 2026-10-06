"""Phase 8 Leads: CRUD, pipeline, notes, conversion, isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads import LeadService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.crm.services import ServicesPricebookService
from callbot_platform.db.models import Tenant, TenantUser
from callbot_platform.organization.membership import MEMBERSHIP_ACTIVE


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _api(session: Session) -> LeadService:
    return LeadService(session)


def _member(
    session: Session, tenant: Tenant, email: str = "owner@test.com"
) -> TenantUser:
    user = TenantUser(
        tenant_id=tenant.id,
        email=email,
        password_hash="x",
        name="Owner",
        role="admin",
        status=MEMBERSHIP_ACTIVE,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def test_lead_crud_search_archive(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    customer = CustomerService(session).create(
        tenant.id, name="Jane Doe", phone="+15551000001", actor="t"
    )
    created = api.create(
        tenant.id,
        title="AC Tune-Up Inquiry",
        source="WEBSITE",
        priority="HIGH",
        customer_id=uuid.UUID(customer["id"]),
        actor="t",
    )
    assert created["status"] == "NEW"
    assert created["source"] == "WEBSITE"
    assert created["priority"] == "HIGH"
    assert created["title"] == "AC Tune-Up Inquiry"
    assert created["customer_id"] == customer["id"]

    found = api.list(tenant.id, q="tune")
    assert len(found["leads"]) == 1
    found = api.list(tenant.id, status="NEW", source="WEBSITE", priority="HIGH")
    assert len(found["leads"]) == 1
    found = api.list(tenant.id, customer_id=uuid.UUID(customer["id"]))
    assert len(found["leads"]) == 1

    updated = api.update(
        tenant.id,
        uuid.UUID(created["id"]),
        title="AC Tune-Up — Updated",
        actor="t",
    )
    assert updated["title"] == "AC Tune-Up — Updated"

    with pytest.raises(CrmError) as status_patch:
        api.update(
            tenant.id,
            uuid.UUID(created["id"]),
            status="QUALIFIED",
            actor="t",
        )
    assert status_patch.value.code == "use_transition"

    archived = api.archive(tenant.id, uuid.UUID(created["id"]), actor="t")
    assert archived["archived_at"] is not None
    assert api.list(tenant.id)["leads"] == []
    restored = api.restore(tenant.id, uuid.UUID(created["id"]), actor="t")
    assert restored["archived_at"] is None


def test_pipeline_transitions_and_activities(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    lead = api.create(tenant.id, title="Pipeline Lead", source="PHONE", actor="t")
    lid = uuid.UUID(lead["id"])

    with pytest.raises(CrmError) as bad:
        api.transition_status(tenant.id, lid, to_status="WON", actor="t")
    assert bad.value.code == "invalid_transition"

    step = api.transition_status(tenant.id, lid, to_status="QUALIFIED", actor="t")
    assert step["status"] == "QUALIFIED"
    step = api.transition_status(tenant.id, lid, to_status="CONTACTED", actor="t")
    assert step["status"] == "CONTACTED"
    step = api.transition_status(tenant.id, lid, to_status="BOOKED", actor="t")
    assert step["status"] == "BOOKED"
    step = api.transition_status(tenant.id, lid, to_status="WON", actor="t")
    assert step["status"] == "WON"

    acts = api.list_activities(tenant.id, lid)
    types = {a["activity_type"] for a in acts["activities"]}
    assert "STATUS_CHANGED" in types
    assert "WON" in types
    assert "CREATED" in types

    # Reopen from LOST
    lost_lead = api.create(tenant.id, title="Lost Lead", actor="t")
    llid = uuid.UUID(lost_lead["id"])
    api.transition_status(tenant.id, llid, to_status="LOST", actor="t")
    reopened = api.transition_status(tenant.id, llid, to_status="NEW", actor="t")
    assert reopened["status"] == "NEW"

    counts = api.pipeline_counts(tenant.id)
    assert counts["counts"]["WON"] >= 1
    assert counts["total"] >= 2


def test_notes_crud(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    lead = api.create(tenant.id, title="Note Lead", actor="t")
    lid = uuid.UUID(lead["id"])
    note = api.notes.create(tenant.id, lid, body="Called customer", actor="t")
    assert note["body"] == "Called customer"
    listed = api.notes.list(tenant.id, lid)
    assert len(listed["notes"]) == 1
    updated = api.notes.update(
        tenant.id, lid, uuid.UUID(note["id"]), body="Follow-up done", actor="t"
    )
    assert updated["body"] == "Follow-up done"
    archived = api.notes.archive(tenant.id, lid, uuid.UUID(note["id"]), actor="t")
    assert archived["archived_at"] is not None
    assert api.notes.list(tenant.id, lid)["notes"] == []


def test_service_product_owner_refs(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    api = _api(session)
    svc = ServicesPricebookService(session).create_service(
        tenant.id, name="Tune-Up", actor="t"
    )
    prod = ProductCatalogService(session).create(tenant.id, name="Filter", actor="t")
    owner = _member(session, tenant)
    other_owner = _member(session, tenant_b, email="other@b.com")

    lead = api.create(
        tenant.id,
        title="Linked",
        service_id=uuid.UUID(svc["id"]),
        product_id=uuid.UUID(prod["id"]),
        owner_user_id=owner.id,
        actor="t",
    )
    assert lead["service"]["name"] == "Tune-Up"
    assert lead["product"]["name"] == "Filter"
    assert lead["owner"]["email"] == "owner@test.com"

    with pytest.raises(CrmError) as cross_owner:
        api.create(
            tenant.id,
            title="Bad Owner",
            owner_user_id=other_owner.id,
            actor="t",
        )
    assert cross_owner.value.code == "owner_not_found"

    b_svc = ServicesPricebookService(session).create_service(
        tenant_b.id, name="Other Svc", actor="t"
    )
    with pytest.raises(CrmError) as cross_svc:
        api.create(
            tenant.id,
            title="Bad Svc",
            service_id=uuid.UUID(b_svc["id"]),
            actor="t",
        )
    assert cross_svc.value.code == "service_not_found"


def test_conversion_existing_and_new_customer(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    existing = CustomerService(session).create(
        tenant.id, name="Existing", phone="+15551000099", actor="t"
    )
    lead = api.create(tenant.id, title="Convert Existing", actor="t")
    result = api.convert(
        tenant.id,
        uuid.UUID(lead["id"]),
        actor="t",
        customer_id=uuid.UUID(existing["id"]),
    )
    assert result["already_converted"] is False
    assert result["conversion"]["customer_id"] == existing["id"]
    assert result["lead"]["customer_id"] == existing["id"]
    assert result["lead"]["converted_at"] is not None

    again = api.convert(
        tenant.id,
        uuid.UUID(lead["id"]),
        actor="t",
        customer_id=uuid.UUID(existing["id"]),
    )
    assert again["already_converted"] is True

    lead2 = api.create(
        tenant.id,
        title="Convert New",
        prospect_name="Prospect",
        prospect_phone="+15551000100",
        actor="t",
    )
    created = api.convert(
        tenant.id,
        uuid.UUID(lead2["id"]),
        actor="t",
        create_customer={"name": "Prospect", "phone": "+15551000100"},
    )
    assert created["already_converted"] is False
    assert created["conversion"]["created_customer"] is True


def test_tenant_isolation_idor(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    api = _api(session)
    lead = api.create(tenant.id, title="Secret Lead", actor="t")
    lid = uuid.UUID(lead["id"])

    with pytest.raises(CrmError) as get_x:
        api.get(tenant_b.id, lid)
    assert get_x.value.code == "not_found"

    with pytest.raises(CrmError):
        api.update(tenant_b.id, lid, title="Hacked", actor="evil")
    with pytest.raises(CrmError):
        api.archive(tenant_b.id, lid, actor="evil")
    with pytest.raises(CrmError):
        api.transition_status(tenant_b.id, lid, to_status="QUALIFIED", actor="evil")
    with pytest.raises(CrmError):
        api.notes.create(tenant_b.id, lid, body="x", actor="evil")
    with pytest.raises(CrmError):
        api.convert(
            tenant_b.id,
            lid,
            actor="evil",
            create_customer={"name": "X", "phone": "+15559999999"},
        )

    assert api.list(tenant_b.id)["leads"] == []
    assert api.get(tenant.id, lid)["title"] == "Secret Lead"


def test_cursor_pagination_stable(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    for i in range(15):
        api.create(tenant.id, title=f"Lead {i:02d}", actor="t")
    page1 = api.list(tenant.id, limit=5)
    assert len(page1["leads"]) == 5
    assert page1["next_cursor"]
    page2 = api.list(tenant.id, limit=5, cursor=page1["next_cursor"])
    assert len(page2["leads"]) == 5
    ids1 = {r["id"] for r in page1["leads"]}
    ids2 = {r["id"] for r in page2["leads"]}
    assert ids1.isdisjoint(ids2)


def test_search_volume(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    owner = _member(session, tenant)
    for i in range(520):
        api.create(
            tenant.id,
            title=f"Bulk Lead {i}",
            source="PHONE" if i % 2 == 0 else "WEBSITE",
            priority="HIGH" if i % 5 == 0 else "MEDIUM",
            owner_user_id=owner.id if i % 3 == 0 else None,
            actor="t",
        )
    phone = api.list(tenant.id, source="PHONE", limit=50)
    assert len(phone["leads"]) == 50
    assert phone["next_cursor"]
    high = api.list(tenant.id, priority="HIGH", limit=200)
    assert len(high["leads"]) == 104  # 0,5,...,515
    owned = api.list(tenant.id, owner_user_id=owner.id, limit=200)
    assert len(owned["leads"]) == 174  # 0,3,...,519 → 174
    counts = api.pipeline_counts(tenant.id)
    assert counts["counts"]["NEW"] == 520


def test_unassociated_prospect_lead(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    lead = api.create(
        tenant.id,
        title="Walk-in Prospect",
        source="WALK_IN",
        prospect_name="Sam Prospect",
        prospect_phone="+15551000999",
        prospect_email="sam@example.com",
        actor="t",
    )
    assert lead["customer_id"] is None
    assert lead["prospect_name"] == "Sam Prospect"


def test_voice_create_without_customer(session: Session, tenant: Tenant) -> None:
    from callbot_platform.crm.repos.lead_repo import LeadRepository

    lead = LeadRepository(session).create(
        tenant.id,
        service_type="AC tune-up",
        urgency="high",
        prospect_name="Caller",
        prospect_phone="+15555551234",
        actor="voice-agent",
    )
    assert lead["customer_id"] is None
    assert lead["status"] == "NEW"
    assert lead["priority"] == "HIGH"
    assert lead["source"] == "PHONE"
    assert lead["title"] == "AC tune-up"


def test_voice_rejects_cross_tenant_customer(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    from callbot_platform.crm.repos.lead_repo import LeadRepository

    foreign = CustomerService(session).create(
        tenant_b.id, name="Foreign", phone="+15555559999", actor="t"
    )
    with pytest.raises(CrmError) as exc:
        LeadRepository(session).create(
            tenant.id,
            customer_id=uuid.UUID(foreign["id"]),
            service_type="Leak",
        )
    assert exc.value.code == "customer_not_found"


def test_conversion_idempotency_no_duplicate_activity(
    session: Session, tenant: Tenant
) -> None:
    api = _api(session)
    lead = api.create(
        tenant.id,
        title="Idem Convert",
        prospect_name="Pat",
        prospect_phone="+15555550111",
        actor="t",
    )
    lid = uuid.UUID(lead["id"])
    first = api.convert(
        tenant.id,
        lid,
        actor="t",
        create_customer={"name": "Pat", "phone": "+15555550111"},
    )
    assert first["already_converted"] is False
    acts1 = api.list_activities(tenant.id, lid)
    converted1 = [a for a in acts1["activities"] if a["activity_type"] == "CONVERTED"]
    assert len(converted1) == 1

    second = api.convert(
        tenant.id,
        lid,
        actor="t",
        create_customer={"name": "Pat", "phone": "+15555550111"},
    )
    assert second["already_converted"] is True
    assert second["conversion"]["id"] == first["conversion"]["id"]
    acts2 = api.list_activities(tenant.id, lid)
    converted2 = [a for a in acts2["activities"] if a["activity_type"] == "CONVERTED"]
    assert len(converted2) == 1


def test_archived_lead_mutations_blocked(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    lead = api.create(tenant.id, title="Archive Me", actor="t")
    lid = uuid.UUID(lead["id"])
    api.archive(tenant.id, lid, actor="t")

    with pytest.raises(CrmError) as upd:
        api.update(tenant.id, lid, title="Nope", actor="t")
    assert upd.value.code == "lead_archived"

    with pytest.raises(CrmError) as tr:
        api.transition_status(tenant.id, lid, to_status="QUALIFIED", actor="t")
    assert tr.value.code == "lead_archived"

    with pytest.raises(CrmError) as cv:
        api.convert(
            tenant.id,
            lid,
            actor="t",
            create_customer={"name": "X", "phone": "+15555550222"},
        )
    assert cv.value.code == "lead_archived"

    with pytest.raises(CrmError) as note:
        api.notes.create(tenant.id, lid, body="nope", actor="t")
    assert note.value.code == "lead_archived"

    restored = api.restore(tenant.id, lid, actor="t")
    assert restored["archived_at"] is None
    api.transition_status(tenant.id, lid, to_status="QUALIFIED", actor="t")


def test_conversion_matches_existing_by_phone(session: Session, tenant: Tenant) -> None:
    api = _api(session)
    existing = CustomerService(session).create(
        tenant.id, name="Known", phone="+15555550333", actor="t"
    )
    lead = api.create(
        tenant.id,
        title="Match Phone",
        prospect_phone="+15555550333",
        actor="t",
    )
    result = api.convert(
        tenant.id,
        uuid.UUID(lead["id"]),
        actor="t",
        create_customer={"name": "Different Name", "phone": "+15555550333"},
    )
    assert result["conversion"]["created_customer"] is False
    assert result["conversion"]["customer_id"] == existing["id"]


def test_customer_timeline_includes_lead_activity(
    session: Session, tenant: Tenant
) -> None:
    api = _api(session)
    customer = CustomerService(session).create(
        tenant.id, name="Timeline Cust", phone="+15555550444", actor="t"
    )
    lead = api.create(
        tenant.id,
        title="Timeline Lead",
        customer_id=uuid.UUID(customer["id"]),
        actor="t",
    )
    api.transition_status(
        tenant.id, uuid.UUID(lead["id"]), to_status="QUALIFIED", actor="t"
    )
    timeline = CustomerService(session).get_customer_timeline(
        tenant.id,
        uuid.UUID(customer["id"]),
        allowed_types=frozenset({"LEAD"}),
    )
    sources = {item["source"] for item in timeline["items"]}
    assert "leads" in sources
    assert "lead_activities" in sources
