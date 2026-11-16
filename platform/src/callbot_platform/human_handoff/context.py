"""Immutable handoff context snapshot (Phase 24.2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.call_intelligence import CallIntelligenceService
from callbot_platform.db.models.crm import Call, Customer
from callbot_platform.db.models.jobs import Job
from callbot_platform.db.models.scheduling import Appointment
from callbot_platform.human_handoff.emergency import detect_emergency
from callbot_platform.human_handoff.hours import HandoffHoursService


class HandoffContextService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def build_snapshot(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID | None = None,
        conversation_id: UUID | None = None,
        customer_id: UUID | None = None,
        summary: str | None = None,
        transfer_reason: str | None = None,
        department: str | None = None,
        explicit_emergency: bool = False,
        actor: str = "system",
    ) -> dict[str, Any]:
        """Build immutable snapshot saved at handoff creation. Prefer domain facts."""
        call: Call | None = None
        if call_id is not None:
            call = self._session.scalar(
                select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
            )
            if call is not None and customer_id is None:
                customer_id = call.customer_id

        customer_payload: dict[str, Any] | None = None
        if customer_id is not None:
            cust = self._session.scalar(
                select(Customer).where(
                    Customer.id == customer_id, Customer.tenant_id == tenant_id
                )
            )
            if cust is not None:
                customer_payload = {
                    "id": str(cust.id),
                    "name": cust.name,
                    "email": cust.email,
                    "status": cust.status,
                }

        intel: dict[str, Any] | None = None
        transcript: dict[str, Any] | None = None
        recording: dict[str, Any] | None = None
        classification = None
        sentiment = None
        intent = None
        if call_id is not None:
            ci = CallIntelligenceService(self._session)
            try:
                intel = ci.analysis.get_latest(tenant_id, call_id)
            except Exception:
                intel = None
            try:
                transcript = ci.transcripts.get_for_call(
                    tenant_id, call_id, include_segments=True
                )
            except Exception:
                transcript = None
            try:
                recording = ci.recordings.get_for_call(tenant_id, call_id)
            except Exception:
                recording = None
            if intel:
                classification = intel.get("classification")
                sentiment = intel.get("sentiment")
                intent = intel.get("intent")
                if not summary:
                    summary = intel.get("outcome") or intel.get("problem")

        jobs = self._open_jobs(tenant_id, customer_id)
        appointments = self._open_appointments(tenant_id, customer_id, call_id)
        ai_actions = self._recent_ai_actions(
            tenant_id, call_id=call_id, customer_id=customer_id
        )
        hours = HandoffHoursService(self._session).status_at(tenant_id)

        text_for_emergency = " ".join(
            filter(
                None,
                [
                    summary,
                    (transcript or {}).get("full_text") if transcript else None,
                ],
            )
        )
        emergency = detect_emergency(
            text=text_for_emergency,
            classification=classification,
            classification_confidence=(
                float(intel["classification_confidence"])
                if intel and intel.get("classification_confidence") is not None
                else None
            ),
            explicit_emergency=explicit_emergency,
        )

        # Do not embed signed URLs in stored snapshot (security).
        recording_meta = None
        if recording:
            recording_meta = {
                "id": recording.get("id"),
                "status": recording.get("status"),
                "duration_ms": recording.get("duration_ms"),
                "mime_type": recording.get("mime_type"),
            }

        return {
            "customer": customer_payload,
            "intent": intent,
            "summary": (summary or "")[:4000] or None,
            "transcript": {
                "id": transcript.get("id") if transcript else None,
                "status": transcript.get("status") if transcript else None,
                "full_text": transcript.get("full_text") if transcript else None,
                "segments": (transcript.get("segments") or [])[:200]
                if transcript
                else [],
            }
            if transcript
            else None,
            "sentiment": sentiment,
            "classification": classification,
            "jobs": jobs,
            "appointments": appointments,
            "ai_actions": ai_actions,
            "recording": recording_meta,
            "recording_url": None,  # generated on read with auth
            "emergency": emergency,
            "business_hours": hours,
            "transfer_reason": transfer_reason,
            "department": department,
            "channel_refs": {
                "call_id": str(call_id) if call_id else None,
                "conversation_id": str(conversation_id) if conversation_id else None,
            },
            "snapshot_actor": actor,
        }

    def _open_jobs(
        self, tenant_id: UUID, customer_id: UUID | None
    ) -> list[dict[str, Any]]:
        if customer_id is None:
            return []
        rows = list(
            self._session.scalars(
                select(Job)
                .where(
                    Job.tenant_id == tenant_id,
                    Job.customer_id == customer_id,
                    Job.archived_at.is_(None),
                    Job.status.notin_(["COMPLETED", "CANCELLED", "CLOSED"]),
                )
                .order_by(Job.created_at.desc())
                .limit(10)
            ).all()
        )
        return [
            {
                "id": str(j.id),
                "job_number": j.job_number,
                "status": j.status,
                "service_type": j.service_type,
                "priority": j.priority,
            }
            for j in rows
        ]

    def _open_appointments(
        self,
        tenant_id: UUID,
        customer_id: UUID | None,
        call_id: UUID | None,
    ) -> list[dict[str, Any]]:
        stmt = select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.status.notin_(["CANCELLED", "COMPLETED", "NO_SHOW"]),
        )
        if customer_id is not None:
            stmt = stmt.where(Appointment.customer_id == customer_id)
        elif call_id is not None:
            stmt = stmt.where(Appointment.call_id == call_id)
        else:
            return []
        rows = list(
            self._session.scalars(
                stmt.order_by(Appointment.starts_at.desc()).limit(10)
            ).all()
        )
        return [
            {
                "id": str(a.id),
                "confirmation_code": a.confirmation_code,
                "status": a.status,
                "starts_at": a.starts_at.isoformat() if a.starts_at else None,
            }
            for a in rows
        ]

    def _recent_ai_actions(
        self,
        tenant_id: UUID,
        *,
        call_id: UUID | None,
        customer_id: UUID | None,
    ) -> list[dict[str, Any]]:
        from callbot_platform.db.models import TelephonyAuditEvent as Audit

        stmt = (
            select(Audit)
            .where(
                Audit.tenant_id == tenant_id,
                Audit.action.like("ai_%"),
            )
            .order_by(Audit.created_at.desc())
            .limit(25)
        )
        rows = list(self._session.scalars(stmt).all())
        out: list[dict[str, Any]] = []
        for row in rows:
            ids = row.resource_ids or {}
            if (
                call_id
                and ids.get("call_id")
                and str(ids.get("call_id")) != str(call_id)
            ):
                continue
            # Keep when call matched; otherwise require customer match when filtered.
            if (
                not call_id
                and customer_id
                and ids.get("customer_id")
                and str(ids.get("customer_id")) != str(customer_id)
            ):
                continue
            out.append(
                {
                    "action": row.action,
                    "created_at": row.created_at.isoformat()
                    if row.created_at
                    else None,
                    "resource_ids": ids,
                }
            )
            if len(out) >= 15:
                break
        return out
