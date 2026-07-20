"""Tests for hard plan entitlement enforcement."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from callbot_platform.auth.repos import AuthError, AuthRepository
from callbot_platform.billing.entitlements import EntitlementError, EntitlementGuard
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.db.models import Tenant
from callbot_platform.knowledge.repos import KnowledgeError, KnowledgeRepository
from callbot_platform.security.session import ROLE_DISPATCHER


def _starter_sub(session: Session, tenant: Tenant) -> None:
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
        plan_key="starter",
    )
    row = BillingRepository(session).get_by_tenant(tenant.id)
    assert row is not None
    row.status = "active"
    session.flush()


def test_legacy_tenant_unlimited(session: Session, tenant: Tenant) -> None:
    # No subscription row → no hard cap.
    EntitlementGuard(session).require_capacity(tenant.id, "team_users")


def test_team_users_limit(session: Session, tenant: Tenant) -> None:
    _starter_sub(session, tenant)
    auth = AuthRepository(session)
    for i in range(3):
        auth.create_user(
            tenant.id,
            email=f"user{i}@example.com",
            password="password1",
            name=f"User {i}",
            role=ROLE_DISPATCHER,
        )
    with pytest.raises(AuthError) as exc:
        auth.create_user(
            tenant.id,
            email="overflow@example.com",
            password="password1",
            name="Overflow",
            role=ROLE_DISPATCHER,
        )
    assert exc.value.code == "plan_limit_exceeded"


def test_knowledge_documents_limit(session: Session, tenant: Tenant) -> None:
    _starter_sub(session, tenant)
    repo = KnowledgeRepository(session)
    for i in range(10):
        repo.create(
            tenant.id,
            title=f"Article {i}",
            body=f"Body content for article {i} with enough text.",
        )
    with pytest.raises(KnowledgeError) as exc:
        repo.create(
            tenant.id,
            title="Too many",
            body="Should be rejected by plan limit.",
        )
    assert exc.value.code == "plan_limit_exceeded"


def test_phone_numbers_limit(session: Session, tenant: Tenant) -> None:
    _starter_sub(session, tenant)
    from callbot_platform.db.models import TenantPhoneNumber
    from callbot_platform.domain.enums import (
        AuthMethod,
        ConnectionStatus,
        OnboardingPath,
        ProvisioningState,
        TelephonyProviderId,
        VerificationStatus,
    )

    session.add(
        TenantPhoneNumber(
            tenant_id=tenant.id,
            provider=TelephonyProviderId.TWILIO.value,
            e164="+15551110001",
            connection_status=ConnectionStatus.ACTIVE.value,
            verification_status=VerificationStatus.VERIFIED.value,
            onboarding_path=OnboardingPath.PLATFORM_PURCHASE.value,
            auth_method=AuthMethod.MANUAL.value,
            provisioning_state=ProvisioningState.COMPLETE.value,
        )
    )
    session.flush()
    with pytest.raises(EntitlementError) as exc:
        EntitlementGuard(session).require_capacity(tenant.id, "phone_numbers")
    assert exc.value.code == "plan_limit_exceeded"
