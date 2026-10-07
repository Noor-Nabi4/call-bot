"""Tenant-scoped transcript / intelligence search (PostgreSQL FTS)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session

from callbot_platform.db.models.call_intelligence import (
    CallIntelligence,
    CallTranscript,
)
from callbot_platform.db.models.crm import Call


class CallIntelligenceSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        call_id: UUID | None = None,
        customer_id: UUID | None = None,
        speaker: str | None = None,
        classification: str | None = None,
        sentiment: str | None = None,
        intent: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))

        stmt: Select[Any] = (
            select(CallTranscript, CallIntelligence, Call)
            .outerjoin(
                CallIntelligence,
                (CallIntelligence.transcript_id == CallTranscript.id)
                & (CallIntelligence.tenant_id == CallTranscript.tenant_id)
                & (CallIntelligence.deleted_at.is_(None)),
            )
            .join(
                Call,
                (Call.id == CallTranscript.call_id)
                & (Call.tenant_id == CallTranscript.tenant_id),
            )
            .where(
                CallTranscript.tenant_id == tenant_id,
                CallTranscript.deleted_at.is_(None),
                CallTranscript.lifecycle_status != "DELETED",
            )
        )

        if call_id is not None:
            stmt = stmt.where(CallTranscript.call_id == call_id)
        if customer_id is not None:
            stmt = stmt.where(Call.customer_id == customer_id)
        if classification:
            stmt = stmt.where(CallIntelligence.classification == classification.upper())
        if sentiment:
            stmt = stmt.where(CallIntelligence.sentiment == sentiment.upper())
        if intent:
            stmt = stmt.where(CallIntelligence.intent == intent.upper())
        if date_from is not None:
            stmt = stmt.where(CallTranscript.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(CallTranscript.created_at <= date_to)

        if speaker:
            # Filter via segment existence without leaking other tenants
            stmt = stmt.where(
                text(
                    "EXISTS ("
                    "SELECT 1 FROM call_transcript_segments s "
                    "WHERE s.tenant_id = :tenant_id "
                    "AND s.transcript_id = call_transcripts.id "
                    "AND s.speaker = :speaker"
                    ")"
                ).bindparams(tenant_id=tenant_id, speaker=speaker.upper())
            )

        if q and q.strip():
            query = q.strip()
            dialect = self._session.get_bind().dialect.name
            if dialect == "postgresql" and len(query) >= 3:
                # Prefer FTS when migration-added search_vector exists.
                stmt = stmt.where(
                    or_(
                        text(
                            "call_transcripts.search_vector @@ "
                            "plainto_tsquery('english', :q)"
                        ).bindparams(q=query),
                        CallTranscript.full_text.ilike(f"%{query}%"),
                    )
                )
            else:
                stmt = stmt.where(CallTranscript.full_text.ilike(f"%{query}%"))

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(self._session.scalar(count_stmt) or 0)

        rows = self._session.execute(
            stmt.order_by(CallTranscript.created_at.desc()).limit(limit).offset(offset)
        ).all()

        items: list[dict[str, Any]] = []
        for transcript, intel, call in rows:
            items.append(
                {
                    "transcript_id": str(transcript.id),
                    "call_id": str(transcript.call_id),
                    "customer_id": str(call.customer_id) if call.customer_id else None,
                    "status": transcript.status,
                    "language": transcript.language,
                    "snippet": (transcript.full_text or "")[:280],
                    "classification": intel.classification if intel else None,
                    "sentiment": intel.sentiment if intel else None,
                    "intent": intel.intent if intel else None,
                    "created_at": transcript.created_at.isoformat()
                    if transcript.created_at
                    else None,
                    "call_started_at": call.started_at.isoformat()
                    if call.started_at
                    else None,
                }
            )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
