"""Job notes CRUD (extends existing job_notes table)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs.constants import NOTE_BODY_MAX_LEN
from callbot_platform.crm.jobs.serialize import serialize_note
from callbot_platform.db.models.jobs import Job, JobNote
from callbot_platform.telephony.audit import write_audit


class JobNotesService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _job(self, tenant_id: UUID, job_id: UUID) -> Job:
        job = self._session.scalar(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        if job is None:
            raise CrmError("not_found", "Job not found for tenant")
        if job.archived_at is not None:
            raise CrmError("job_archived", "Job is archived")
        return job

    def list(
        self, tenant_id: UUID, job_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        self._job(tenant_id, job_id)
        q = (
            select(JobNote)
            .where(JobNote.tenant_id == tenant_id, JobNote.job_id == job_id)
            .options(selectinload(JobNote.author))
            .order_by(JobNote.created_at.asc(), JobNote.id.asc())
        )
        if not include_archived:
            q = q.where(JobNote.archived_at.is_(None))
        return [serialize_note(n) for n in self._session.scalars(q).all()]

    def create(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        body: str,
        actor: str,
        author_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._job(tenant_id, job_id)
        text = (body or "").strip()
        if not text:
            raise CrmError("invalid_note", "Note body is required")
        if len(text) > NOTE_BODY_MAX_LEN:
            raise CrmError("invalid_note", "Note body is too long")
        note = JobNote(
            tenant_id=tenant_id,
            job_id=job_id,
            author_user_id=author_user_id,
            body=text,
            updated_by=actor,
        )
        self._session.add(note)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_note_created",
            resource_ids={"job_id": str(job_id), "note_id": str(note.id)},
        )
        note = self._session.scalar(
            select(JobNote)
            .where(JobNote.id == note.id)
            .options(selectinload(JobNote.author))
        )
        assert note is not None
        return serialize_note(note)

    def update(
        self,
        tenant_id: UUID,
        job_id: UUID,
        note_id: UUID,
        *,
        body: str,
        actor: str,
    ) -> dict[str, Any]:
        self._job(tenant_id, job_id)
        note = self._session.scalar(
            select(JobNote)
            .where(
                JobNote.id == note_id,
                JobNote.tenant_id == tenant_id,
                JobNote.job_id == job_id,
            )
            .options(selectinload(JobNote.author))
        )
        if note is None or note.archived_at is not None:
            raise CrmError("not_found", "Note not found")
        text = (body or "").strip()
        if not text:
            raise CrmError("invalid_note", "Note body is required")
        if len(text) > NOTE_BODY_MAX_LEN:
            raise CrmError("invalid_note", "Note body is too long")
        note.body = text
        note.updated_by = actor
        note.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_note_updated",
            resource_ids={"job_id": str(job_id), "note_id": str(note.id)},
        )
        return serialize_note(note)

    def archive(
        self,
        tenant_id: UUID,
        job_id: UUID,
        note_id: UUID,
        *,
        actor: str,
    ) -> dict[str, Any]:
        self._job(tenant_id, job_id)
        note = self._session.scalar(
            select(JobNote).where(
                JobNote.id == note_id,
                JobNote.tenant_id == tenant_id,
                JobNote.job_id == job_id,
            )
        )
        if note is None:
            raise CrmError("not_found", "Note not found")
        if note.archived_at is None:
            note.archived_at = datetime.now(UTC)
            note.updated_by = actor
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="job_note_archived",
                resource_ids={"job_id": str(job_id), "note_id": str(note.id)},
            )
        return serialize_note(note)
