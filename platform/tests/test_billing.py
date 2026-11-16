"""SaaS signup and Stripe subscription billing tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from callbot_platform.async_jobs.runner import run_async_job
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.billing.errors import BillingError
from callbot_platform.billing.plans import VALID_PLAN_KEYS, plan_by_key
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.billing.service import BillingService
from callbot_platform.config import Settings
from callbot_platform.db import get_session_factory
from callbot_platform.db.models import Tenant
from callbot_platform.domain.enums import TenantStatus


def _settings(**overrides: Any) -> Settings:
    base = {
        "stripe_secret_key": "sk_test_dummy",
        "stripe_webhook_secret": "whsec_test_dummy",
        "stripe_checkout_success_url": "http://localhost:3002/settings/billing?checkout=success",
        "stripe_checkout_cancel_url": "http://localhost:3002/signup?canceled=1",
        "stripe_portal_return_url": "http://localhost:3002/settings/billing",
        "session_secret": "test-session-secret",
    }
    base.update(overrides)
    return Settings(**base)


def test_plan_catalog_amounts() -> None:
    assert frozenset({"starter", "growth", "pro"}) == VALID_PLAN_KEYS
    starter = plan_by_key("starter")
    growth = plan_by_key("growth")
    pro = plan_by_key("pro")
    assert starter is not None and starter["unit_amount"] == 9900
    assert growth is not None and growth["unit_amount"] == 24900
    assert pro is not None and pro["unit_amount"] == 49900


def test_list_plans_from_code_catalog() -> None:
    service = BillingService(MagicMock(), _settings())
    catalog = service.pricing_catalog()
    plans = catalog["plans"]
    assert len(plans) == 3
    assert all(p["configured"] for p in plans)
    assert {p["key"] for p in plans} == {"starter", "growth", "pro"}
    by_key = {p["key"]: p for p in plans}
    assert by_key["starter"]["unit_amount"] == 9900
    assert by_key["growth"]["unit_amount"] == 24900
    assert by_key["pro"]["unit_amount"] == 49900
    assert by_key["growth"]["popular"] is True
    assert by_key["starter"]["entitlements"]["monthly_minutes"] == 250
    assert by_key["growth"]["entitlements"]["dispatch_enabled"] is True
    assert by_key["starter"]["entitlements"]["dispatch_enabled"] is False
    assert catalog["enterprise"]["checkoutable"] is False
    assert catalog["trial"]["days"] == 14
    assert (
        catalog["number_pricing"]["platform_purchase"]["us_local_monthly_cents"] == 500
    )


def test_entitlements_for_subscription(session: Session) -> None:
    settings = _settings()
    tenant = Tenant(
        name="Entitled Co",
        slug=f"ent-{uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE.value,
    )
    session.add(tenant)
    session.flush()
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id="cus_ent",
        plan_key="pro",
    )
    session.flush()
    sub = BillingService(session, settings).get_subscription(tenant.id)
    assert sub is not None
    assert sub["entitlements"]["monthly_minutes"] == 2000
    assert sub["entitlements"]["concurrent_calls"] == 10


def test_signup_creates_pending_tenant(session: Session) -> None:
    settings = _settings()
    service = BillingService(session, settings)

    customer = MagicMock(id="cus_test_1")
    checkout = MagicMock(url="https://checkout.stripe.test/session")

    with (
        patch(
            "callbot_platform.async_jobs.handlers.stripe_billing.stripe.Customer.create",
            return_value=customer,
        ),
        patch(
            "callbot_platform.async_jobs.handlers.stripe_billing.stripe.checkout.Session.create",
            return_value=checkout,
        ) as create_session,
    ):
        result = service.signup(
            business_name="Acme HVAC",
            slug=f"acme-{uuid4().hex[:8]}",
            timezone="America/Chicago",
            name="Owner",
            email="owner@acme.test",
            password="password123",
            plan_key="growth",
        )
        session.commit()
        run_async_job(
            get_session_factory(), UUID(str(result["job_id"])), settings=settings
        )
        checkout_info = service.get_signup_checkout(UUID(str(result["tenant_id"])))
        result["checkout_url"] = checkout_info["checkout_url"]

    session.expire_all()
    assert result["checkout_url"] == "https://checkout.stripe.test/session"
    assert result["user"]["email"] == "owner@acme.test"
    assert result["user"]["role"] == "admin"

    # Checkout must use price_data (no registered Stripe Price IDs).
    kwargs = create_session.call_args.kwargs
    line_item = kwargs["line_items"][0]
    assert "price" not in line_item
    assert line_item["price_data"]["unit_amount"] == 24900
    assert line_item["price_data"]["product_data"]["metadata"]["plan_key"] == "growth"

    tenant = session.get(Tenant, UUID(result["user"]["tenant_id"]))
    assert tenant is not None
    assert tenant.status == TenantStatus.PENDING_SUBSCRIPTION.value

    sub = BillingRepository(session).get_by_tenant(tenant.id)
    assert sub is not None
    assert sub.status == "incomplete"
    assert sub.plan_key == "growth"
    assert sub.stripe_customer_id == "cus_test_1"
    assert sub.status != "active"


def test_validate_signup_fields_per_field(session: Session) -> None:
    service = BillingService(session, _settings())
    free = f"free-{uuid4().hex[:8]}"
    ok = service.validate_signup_fields(slug=free, email="owner@acme.test")
    assert ok == {"ok": True, "errors": {}}

    taken_slug = f"taken-{uuid4().hex[:8]}"
    session.add(
        Tenant(
            name="Taken Co",
            slug=taken_slug,
            status=TenantStatus.ACTIVE.value,
        )
    )
    session.flush()

    denied = service.validate_signup_fields(
        slug=taken_slug.upper(),
        email="bad-email",
        plan_key="enterprise",
    )
    assert denied["ok"] is False
    assert denied["errors"]["slug"]["code"] == "slug_taken"
    assert denied["errors"]["email"]["code"] == "invalid_email"
    assert denied["errors"]["plan_key"]["code"] == "invalid_plan"

    # Only provided fields are validated.
    slug_only = service.validate_signup_fields(slug="Bad_Slug")
    assert slug_only["ok"] is False
    assert set(slug_only["errors"]) == {"slug"}
    assert slug_only["errors"]["slug"]["code"] == "invalid_slug"


def test_allocate_signup_slug_from_business_name(session: Session) -> None:
    service = BillingService(session, _settings())
    assert service.slugify_business_name("Acme HVAC Co.") == "acme-hvac-co"
    assert service.slugify_business_name("!!!") == "workspace"

    free_name = f"Fresh HVAC {uuid4().hex[:6]}"
    allocated = service.allocate_signup_slug(free_name)
    assert allocated == service.slugify_business_name(free_name)

    session.add(
        Tenant(
            name=free_name,
            slug=allocated,
            status=TenantStatus.ACTIVE.value,
        )
    )
    session.flush()
    collision = service.allocate_signup_slug(free_name)
    assert collision != allocated
    assert collision.startswith(allocated[:8])


def test_signup_rejects_invalid_plan(session: Session) -> None:
    service = BillingService(session, _settings())
    with pytest.raises(BillingError) as exc:
        service.signup(
            business_name="Acme",
            slug="acme-bad-plan",
            timezone="UTC",
            name="Owner",
            email="o@t.test",
            password="password123",
            plan_key="enterprise",
        )
    assert exc.value.code == "invalid_plan"


def test_webhook_activates_subscription(session: Session) -> None:
    settings = _settings()
    tenant = Tenant(
        name="Webhook Co",
        slug=f"wh-{uuid4().hex[:8]}",
        status=TenantStatus.PENDING_SUBSCRIPTION.value,
    )
    session.add(tenant)
    session.flush()
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="a@t.test",
        password="password123",
        name="Admin",
    )
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id="cus_wh_1",
        plan_key="starter",
    )
    session.flush()

    service = BillingService(session, settings)
    period_end = int(datetime(2026, 8, 1, tzinfo=UTC).timestamp())
    subscription_obj = {
        "id": "sub_wh_1",
        "customer": "cus_wh_1",
        "status": "active",
        "cancel_at_period_end": False,
        "current_period_end": period_end,
        "trial_end": None,
        "metadata": {"tenant_id": str(tenant.id), "plan_key": "starter"},
        "items": {
            "data": [{"price": {"id": "price_auto_from_checkout"}}],
        },
    }
    event = {
        "id": "evt_test_1",
        "type": "customer.subscription.updated",
        "data": {"object": subscription_obj},
    }

    result = service.handle_webhook_event(event)  # type: ignore[arg-type]
    assert result["ok"] is True
    assert result["duplicate"] is False

    session.refresh(tenant)
    assert tenant.status == TenantStatus.ACTIVE.value
    sub = BillingRepository(session).get_by_tenant(tenant.id)
    assert sub is not None
    assert sub.status == "active"
    assert sub.plan_key == "starter"
    assert sub.stripe_subscription_id == "sub_wh_1"
    assert service.tenant_is_entitled(tenant.id)

    replay = service.handle_webhook_event(event)  # type: ignore[arg-type]
    assert replay["duplicate"] is True


def test_invalid_webhook_signature_rejected(session: Session) -> None:
    service = BillingService(session, _settings())
    with pytest.raises(BillingError) as exc:
        service.construct_webhook_event(b"{}", "bad_sig")
    assert exc.value.code == "invalid_signature"


def test_entitlement_gate_legacy_and_incomplete(session: Session) -> None:
    settings = _settings()
    service = BillingService(session, settings)

    legacy = Tenant(name="Legacy", slug=f"leg-{uuid4().hex[:8]}", status="active")
    session.add(legacy)
    session.flush()
    assert service.tenant_is_entitled(legacy.id) is True

    pending = Tenant(
        name="Pending",
        slug=f"pen-{uuid4().hex[:8]}",
        status=TenantStatus.PENDING_SUBSCRIPTION.value,
    )
    session.add(pending)
    session.flush()
    BillingRepository(session).create_incomplete(
        tenant_id=pending.id,
        stripe_customer_id="cus_pen",
        plan_key="pro",
    )
    session.flush()
    assert service.tenant_is_entitled(pending.id) is False


def test_checkout_session_completed_does_not_activate_without_sub(
    session: Session,
) -> None:
    """checkout.session.completed alone must not invent an active status."""
    settings = _settings()
    tenant = Tenant(
        name="Checkout Only",
        slug=f"co-{uuid4().hex[:8]}",
        status=TenantStatus.PENDING_SUBSCRIPTION.value,
    )
    session.add(tenant)
    session.flush()
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id="cus_co",
        plan_key="starter",
    )
    session.flush()

    service = BillingService(session, settings)
    event = {
        "id": "evt_co_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_co",
                "client_reference_id": str(tenant.id),
                "subscription": None,
            }
        },
    }
    service.handle_webhook_event(event)  # type: ignore[arg-type]
    session.refresh(tenant)
    assert tenant.status == TenantStatus.PENDING_SUBSCRIPTION.value
    sub = BillingRepository(session).get_by_tenant(tenant.id)
    assert sub is not None
    assert sub.status == "incomplete"
