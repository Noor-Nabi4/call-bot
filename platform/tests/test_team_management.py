"""Tests for admin team user management."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from callbot_platform.auth.repos import AuthError, AuthRepository
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.db.models import Tenant
from callbot_platform.security.session import ROLE_ADMIN, ROLE_DISPATCHER


def test_update_role_and_deactivate(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    admin = auth.create_user(
        tenant.id,
        email="admin@example.com",
        password="password1",
        name="Admin",
        role=ROLE_ADMIN,
    )
    member = auth.create_user(
        tenant.id,
        email="member@example.com",
        password="password1",
        name="Member",
        role=ROLE_DISPATCHER,
    )
    updated = auth.update_user_admin(
        tenant.id,
        uuid.UUID(member["id"]),
        actor_user_id=uuid.UUID(admin["id"]),
        actor_email=admin["email"],
        role=ROLE_ADMIN,
    )
    assert updated["role"] == ROLE_ADMIN

    deactivated = auth.update_user_admin(
        tenant.id,
        uuid.UUID(member["id"]),
        actor_user_id=uuid.UUID(admin["id"]),
        actor_email=admin["email"],
        is_active=False,
    )
    assert deactivated["is_active"] is False


def test_cannot_deactivate_self_or_last_admin(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    admin = auth.create_user(
        tenant.id,
        email="solo@example.com",
        password="password1",
        name="Solo",
        role=ROLE_ADMIN,
    )
    admin_id = uuid.UUID(admin["id"])
    with pytest.raises(AuthError) as self_exc:
        auth.update_user_admin(
            tenant.id,
            admin_id,
            actor_user_id=admin_id,
            actor_email=admin["email"],
            is_active=False,
        )
    assert self_exc.value.code == "cannot_deactivate_self"

    other = auth.create_user(
        tenant.id,
        email="other@example.com",
        password="password1",
        name="Other",
        role=ROLE_DISPATCHER,
    )
    with pytest.raises(AuthError) as last_exc:
        auth.update_user_admin(
            tenant.id,
            admin_id,
            actor_user_id=uuid.UUID(other["id"]),
            actor_email=other["email"],
            is_active=False,
        )
    assert last_exc.value.code == "last_admin"


def test_reactivate_respects_seat_limit(session: Session, tenant: Tenant) -> None:
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
        plan_key="starter",
    )
    row = BillingRepository(session).get_by_tenant(tenant.id)
    assert row is not None
    row.status = "active"
    session.flush()

    auth = AuthRepository(session)
    admin = auth.create_user(
        tenant.id,
        email="a@example.com",
        password="password1",
        name="A",
        role=ROLE_ADMIN,
    )
    u1 = auth.create_user(
        tenant.id,
        email="b@example.com",
        password="password1",
        name="B",
        role=ROLE_DISPATCHER,
    )
    u2 = auth.create_user(
        tenant.id,
        email="c@example.com",
        password="password1",
        name="C",
        role=ROLE_DISPATCHER,
    )
    auth.update_user_admin(
        tenant.id,
        uuid.UUID(u2["id"]),
        actor_user_id=uuid.UUID(admin["id"]),
        actor_email=admin["email"],
        is_active=False,
    )
    # Still 2 active; create third to fill seats, then fail reactivate of u2.
    auth.create_user(
        tenant.id,
        email="d@example.com",
        password="password1",
        name="D",
        role=ROLE_DISPATCHER,
    )
    with pytest.raises(AuthError) as exc:
        auth.update_user_admin(
            tenant.id,
            uuid.UUID(u2["id"]),
            actor_user_id=uuid.UUID(admin["id"]),
            actor_email=admin["email"],
            is_active=True,
        )
    assert exc.value.code == "plan_limit_exceeded"
    _ = u1
