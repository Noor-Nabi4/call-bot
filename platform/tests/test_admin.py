"""Admin metrics and retention tests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from callbot_platform.admin.repos import AdminRepository
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.crm.repos import CustomerRepository
from callbot_platform.db.models import Tenant


def test_metrics_and_retention(session: Session, tenant: Tenant) -> None:
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    CustomerRepository(session).upsert(
        tenant.id, name="Cust", phone="+15550001111"
    )
    admin = AdminRepository(session)
    metrics = admin.metrics_summary(tenant.id, days=30)
    assert metrics["customers"] >= 1
    settings = admin.upsert_retention(
        tenant.id, recording_retention_days=14, actor="admin@t.test"
    )
    assert settings["recording_retention_days"] == 14
    users = admin.list_users(tenant.id)
    assert any(u["email"] == "admin@t.test" for u in users)
