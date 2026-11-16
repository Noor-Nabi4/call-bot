"""Lead activity recording."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads.constants import LEAD_ACTIVITY_TYPES
from callbot_platform.db.models import LeadActivity


class LeadActivityService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        activity_type: str,
        actor: str | None = None,
        actor_user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LeadActivity:
        if activity_type not in LEAD_ACTIVITY_TYPES:
            raise CrmError("invalid_activity_type", "Unknown lead activity type")
        row = LeadActivity(
            tenant_id=tenant_id,
            lead_id=lead_id,
            activity_type=activity_type,
            actor=actor,
            actor_user_id=actor_user_id,
            metadata_json=dict(metadata or {}),
        )
        self._session.add(row)
        self._session.flush()
        return row
