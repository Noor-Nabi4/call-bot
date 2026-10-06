"""Lead notes CRUD."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads.activities import LeadActivityService
from callbot_platform.crm.leads.constants import LeadActivityType
from callbot_platform.crm.leads.cursors import LeadCursor, parse_lead_page
from callbot_platform.crm.leads.serialize import serialize_note
from callbot_platform.db.models import Lead, LeadNote
from callbot_platform.telephony.audit import write_audit


class LeadNotesService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._activities = LeadActivityService(session)

    def _lead(self, tenant_id: UUID, lead_id: UUID, *, for_mutation: bool) -> Lead:
        lead = self._session.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        )
        if lead is None:
            raise CrmError("not_found", "Lead not found for tenant")
        if for_mutation and lead.archived_at is not None:
            raise CrmError("lead_archived", "Cannot mutate notes on an archived lead")
        return lead

    def list(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        include_archived: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        self._lead(tenant_id, lead_id, for_mutation=False)
        try:
            page, decoded = parse_lead_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        q = select(LeadNote).where(
            LeadNote.tenant_id == tenant_id, LeadNote.lead_id == lead_id
        )
        if not include_archived:
            q = q.where(LeadNote.archived_at.is_(None))
        if decoded is not None:
            q = q.where(
                (LeadNote.created_at < decoded.created_at)
                | (
                    (LeadNote.created_at == decoded.created_at)
                    & (LeadNote.id < decoded.id)
                )
            )
        q = q.order_by(LeadNote.created_at.desc(), LeadNote.id.desc()).limit(
            page.limit + 1
        )
        rows = list(self._session.scalars(q).all())
        next_cursor = None
        if len(rows) > page.limit:
            rows = rows[: page.limit]
            last = rows[-1]
            next_cursor = LeadCursor(created_at=last.created_at, id=last.id).encode()
        return {
            "notes": [serialize_note(r) for r in rows],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }

    def create(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        body: str,
        actor: str,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._lead(tenant_id, lead_id, for_mutation=True)
        cleaned = (body or "").strip()
        if not cleaned:
            raise CrmError("invalid_body", "Note body is required")
        if len(cleaned) > 20000:
            raise CrmError("invalid_body", "Note body is too long")
        note = LeadNote(
            tenant_id=tenant_id,
            lead_id=lead_id,
            body=cleaned,
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(note)
        self._session.flush()
        self._activities.record(
            tenant_id,
            lead_id,
            activity_type=LeadActivityType.NOTE_ADDED.value,
            actor=actor,
            actor_user_id=actor_user_id,
            metadata={"note_id": str(note.id)},
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="lead_note_created",
            resource_ids={"lead_id": str(lead_id), "note_id": str(note.id)},
        )
        return serialize_note(note)

    def update(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        note_id: UUID,
        *,
        body: str,
        actor: str,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._lead(tenant_id, lead_id, for_mutation=True)
        note = self._session.scalar(
            select(LeadNote).where(
                LeadNote.id == note_id,
                LeadNote.tenant_id == tenant_id,
                LeadNote.lead_id == lead_id,
            )
        )
        if note is None:
            raise CrmError("not_found", "Lead note not found")
        if note.archived_at is not None:
            raise CrmError("note_archived", "Cannot update an archived note")
        cleaned = (body or "").strip()
        if not cleaned:
            raise CrmError("invalid_body", "Note body is required")
        note.body = cleaned
        note.updated_by = actor
        note.updated_at = datetime.now(UTC)
        self._session.flush()
        self._activities.record(
            tenant_id,
            lead_id,
            activity_type=LeadActivityType.NOTE_UPDATED.value,
            actor=actor,
            actor_user_id=actor_user_id,
            metadata={"note_id": str(note.id)},
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="lead_note_updated",
            resource_ids={"lead_id": str(lead_id), "note_id": str(note.id)},
        )
        return serialize_note(note)

    def archive(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        note_id: UUID,
        *,
        actor: str,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._lead(tenant_id, lead_id, for_mutation=True)
        note = self._session.scalar(
            select(LeadNote).where(
                LeadNote.id == note_id,
                LeadNote.tenant_id == tenant_id,
                LeadNote.lead_id == lead_id,
            )
        )
        if note is None:
            raise CrmError("not_found", "Lead note not found")
        if note.archived_at is None:
            note.archived_at = datetime.now(UTC)
            note.updated_by = actor
            self._session.flush()
            self._activities.record(
                tenant_id,
                lead_id,
                activity_type=LeadActivityType.NOTE_DELETED.value,
                actor=actor,
                actor_user_id=actor_user_id,
                metadata={"note_id": str(note.id)},
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="lead_note_archived",
                resource_ids={"lead_id": str(lead_id), "note_id": str(note.id)},
            )
        return serialize_note(note)
