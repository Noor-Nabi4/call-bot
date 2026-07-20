"""White-label branding tests."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from callbot_platform.branding import BrandingError, BrandingRepository
from callbot_platform.db.models import Tenant


def test_branding_upsert_and_validation(session: Session, tenant: Tenant) -> None:
    repo = BrandingRepository(session)
    empty = repo.get(tenant.id)
    assert empty["product_name"] is None

    saved = repo.upsert(
        tenant.id,
        actor="admin@t.test",
        product_name="Acme Voice",
        logo_url="https://cdn.example.com/logo.png",
        primary_color="#1F6F5B",
        accent_color="#0ea5e9",
        support_email="help@acme.test",
    )
    assert saved["product_name"] == "Acme Voice"
    assert saved["primary_color"] == "#1f6f5b"
    assert saved["logo_url"].startswith("https://")

    with pytest.raises(BrandingError):
        repo.upsert(tenant.id, actor="admin@t.test", primary_color="teal")
    with pytest.raises(BrandingError):
        repo.upsert(tenant.id, actor="admin@t.test", logo_url="ftp://x/logo.png")
