"""Call quality validation and review tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from callbot_platform.admin.repos import AdminError, AdminRepository
from callbot_platform.call_quality import CallQualityError, validate_quality_review
from callbot_platform.crm.repos import CallRepository
from callbot_platform.db.models import Tenant


def test_validate_quality_review_requires_fields() -> None:
    with pytest.raises(CallQualityError) as exc:
        validate_quality_review()
    assert exc.value.code == "invalid_quality_review"


def test_validate_quality_score_bounds() -> None:
    with pytest.raises(CallQualityError):
        validate_quality_review(quality_score=0)
    with pytest.raises(CallQualityError):
        validate_quality_review(quality_score=6)
    ok = validate_quality_review(quality_score=4, disposition_code="Resolved")
    assert ok["quality_score"] == 4
    assert ok["disposition_code"] == "resolved"


def test_review_call_quality(session: Session, tenant: Tenant) -> None:
    repo = CallRepository(session)
    started = repo.start(tenant.id, room_name="qa-room", caller_number="+15550008888")
    call_id = uuid.UUID(started["id"])
    admin = AdminRepository(session)

    with pytest.raises(AdminError) as active_exc:
        admin.review_call_quality(
            tenant.id, call_id, actor="admin@t.test", quality_score=5
        )
    assert active_exc.value.code == "call_still_active"

    repo.end(tenant.id, call_id=call_id, status="closed", disconnect_reason="completed")
    reviewed = admin.review_call_quality(
        tenant.id,
        call_id,
        actor="admin@t.test",
        quality_score=5,
        disposition_code="resolved",
        quality_notes="Clear greeting and booking.",
    )
    assert reviewed["quality_score"] == 5
    assert reviewed["disposition_code"] == "resolved"
    assert reviewed["quality_reviewed_by"] == "admin@t.test"

    metrics = admin.metrics_summary(tenant.id, days=7)
    assert metrics["quality_reviews"] >= 1
    assert metrics["avg_quality_score"] == 5.0
