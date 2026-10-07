"""AI analysis + classification (Phase 23). LLM never mutates CRM state."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.call_intelligence.constants import (
    ANALYSIS_VERSION,
    APPOINTMENT_STATUS_MAP,
    MAX_ANALYZE_ATTEMPTS,
    AppointmentIntelStatus,
    CallClassification,
    CallIntent,
    ClassificationSource,
    LifecycleStatus,
    ProcessingStatus,
)
from callbot_platform.call_intelligence.errors import CallIntelligenceError
from callbot_platform.call_intelligence.providers import (
    AnalysisProvider,
    get_analysis_provider,
)
from callbot_platform.call_intelligence.retention import (
    expires_at,
    load_retention_policy,
)
from callbot_platform.call_intelligence.serialize import serialize_intelligence
from callbot_platform.call_intelligence.validation import content_hash
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.call_intelligence import (
    CallIntelligence,
    CallTranscript,
)
from callbot_platform.db.models.crm import Call
from callbot_platform.db.models.scheduling import Appointment

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        provider: AnalysisProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._provider = provider or get_analysis_provider(self._settings)

    def _require_call(self, tenant_id: UUID, call_id: UUID) -> Call:
        row = self._session.scalar(
            select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
        )
        if row is None:
            raise CallIntelligenceError("call_not_found", "Call not found for tenant")
        return row

    def resolve_appointment_status(self, tenant_id: UUID, call_id: UUID) -> str:
        """Prefer authoritative Appointment domain state over transcript claims."""
        appt = self._session.scalar(
            select(Appointment)
            .where(
                Appointment.tenant_id == tenant_id,
                Appointment.call_id == call_id,
            )
            .order_by(Appointment.created_at.desc())
            .limit(1)
        )
        if appt is None:
            return AppointmentIntelStatus.NONE.value
        return APPOINTMENT_STATUS_MAP.get(
            str(appt.status).upper(), AppointmentIntelStatus.UNKNOWN.value
        )

    def _rule_signals(self, call: Call) -> dict[str, Any]:
        metrics = call.metrics if isinstance(call.metrics, dict) else {}
        disposition = (call.disposition_code or "").lower()
        return {
            "human_transfer": bool(
                metrics.get("handoff_requested")
                or metrics.get("human_transfer")
                or disposition == "transferred"
            ),
            "spam": disposition == "spam" or bool(metrics.get("spam")),
            "disposition": call.disposition_code,
            "booking_tool": bool(metrics.get("booking_completed")),
            "cancellation_tool": bool(metrics.get("cancellation_completed")),
        }

    def get_latest(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        self._require_call(tenant_id, call_id)
        row = self._session.scalar(
            select(CallIntelligence)
            .where(
                CallIntelligence.tenant_id == tenant_id,
                CallIntelligence.call_id == call_id,
                CallIntelligence.deleted_at.is_(None),
                CallIntelligence.lifecycle_status != LifecycleStatus.DELETED.value,
            )
            .order_by(CallIntelligence.analysis_version.desc())
            .limit(1)
        )
        if row is None:
            return None
        return serialize_intelligence(row)

    def get_classification(
        self, tenant_id: UUID, call_id: UUID
    ) -> dict[str, Any] | None:
        intel = self.get_latest(tenant_id, call_id)
        if intel is None:
            return None
        return {
            "call_id": intel["call_id"],
            "classification": intel["classification"],
            "confidence": intel["classification_confidence"],
            "source": intel["classification_source"],
            "model": intel["model"],
            "model_version": intel["model_version"],
            "created_at": intel["created_at"],
            "analysis_status": intel["analysis_status"],
        }

    def _claim_or_create_row(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        transcript_id: UUID,
        input_hash: str,
        force_new_version: bool,
    ) -> CallIntelligence:
        if not force_new_version:
            by_hash = self._session.scalar(
                select(CallIntelligence).where(
                    CallIntelligence.tenant_id == tenant_id,
                    CallIntelligence.call_id == call_id,
                    CallIntelligence.input_hash == input_hash,
                    CallIntelligence.deleted_at.is_(None),
                    CallIntelligence.analysis_status.in_(
                        [
                            ProcessingStatus.PENDING.value,
                            ProcessingStatus.PROCESSING.value,
                            ProcessingStatus.COMPLETED.value,
                        ]
                    ),
                )
            )
            if by_hash is not None:
                return by_hash

        max_ver = self._session.scalar(
            select(func.coalesce(func.max(CallIntelligence.analysis_version), 0)).where(
                CallIntelligence.tenant_id == tenant_id,
                CallIntelligence.call_id == call_id,
            )
        )
        next_ver = int(max_ver or 0) + 1
        policy = load_retention_policy(
            self._session, tenant_id, settings=self._settings
        )
        row = CallIntelligence(
            tenant_id=tenant_id,
            call_id=call_id,
            transcript_id=transcript_id,
            analysis_status=ProcessingStatus.PENDING.value,
            analysis_version=next_ver,
            input_hash=input_hash,
            lifecycle_status=LifecycleStatus.ACTIVE.value,
            expires_at=expires_at(policy.analysis_retention_days),
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            self._session.expire_all()
            again = self._session.scalar(
                select(CallIntelligence).where(
                    CallIntelligence.tenant_id == tenant_id,
                    CallIntelligence.call_id == call_id,
                    CallIntelligence.input_hash == input_hash,
                    CallIntelligence.deleted_at.is_(None),
                )
            )
            if again is not None:
                return again
            # Version conflict — retry with bumped version
            max_ver2 = self._session.scalar(
                select(
                    func.coalesce(func.max(CallIntelligence.analysis_version), 0)
                ).where(
                    CallIntelligence.tenant_id == tenant_id,
                    CallIntelligence.call_id == call_id,
                )
            )
            row = CallIntelligence(
                tenant_id=tenant_id,
                call_id=call_id,
                transcript_id=transcript_id,
                analysis_status=ProcessingStatus.PENDING.value,
                analysis_version=int(max_ver2 or 0) + 1,
                input_hash=input_hash,
                lifecycle_status=LifecycleStatus.ACTIVE.value,
                expires_at=expires_at(policy.analysis_retention_days),
            )
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        return row

    def analyze_transcript(
        self,
        *,
        tenant_id: UUID,
        transcript_id: UUID,
        force_new_version: bool = False,
    ) -> dict[str, Any]:
        transcript = self._session.scalar(
            select(CallTranscript).where(
                CallTranscript.id == transcript_id,
                CallTranscript.tenant_id == tenant_id,
                CallTranscript.deleted_at.is_(None),
            )
        )
        if transcript is None:
            raise CallIntelligenceError(
                "transcript_not_found", "Transcript not found for tenant"
            )
        if transcript.status != ProcessingStatus.COMPLETED.value:
            raise CallIntelligenceError(
                "transcript_not_ready", "Transcript not completed"
            )

        call = self._require_call(tenant_id, transcript.call_id)
        input_hash = content_hash(
            str(transcript.id),
            transcript.full_text or "",
            str(ANALYSIS_VERSION),
        )
        if force_new_version:
            max_ver = self._session.scalar(
                select(
                    func.coalesce(func.max(CallIntelligence.analysis_version), 0)
                ).where(
                    CallIntelligence.tenant_id == tenant_id,
                    CallIntelligence.call_id == transcript.call_id,
                )
            )
            input_hash = content_hash(input_hash, f"force:{int(max_ver or 0) + 1}")

        row = self._claim_or_create_row(
            tenant_id=tenant_id,
            call_id=transcript.call_id,
            transcript_id=transcript.id,
            input_hash=input_hash,
            force_new_version=force_new_version,
        )

        if (
            row.analysis_status == ProcessingStatus.COMPLETED.value
            and not force_new_version
        ):
            return serialize_intelligence(row)

        if row.attempt_count >= MAX_ANALYZE_ATTEMPTS:
            row.analysis_status = ProcessingStatus.FAILED.value
            row.last_error = "max_attempts_exceeded"
            self._session.flush()
            return serialize_intelligence(row)

        row.analysis_status = ProcessingStatus.PROCESSING.value
        row.attempt_count = int(row.attempt_count) + 1
        row.started_at = datetime.now(UTC)
        row.transcript_id = transcript.id
        row.input_hash = input_hash
        row.last_error = None
        self._session.flush()

        signals = self._rule_signals(call)
        appt_status = self.resolve_appointment_status(tenant_id, transcript.call_id)
        signals["appointment_status"] = appt_status

        rule_class: str | None = None
        if signals["human_transfer"]:
            rule_class = CallClassification.HUMAN_TRANSFER.value
        elif signals["spam"]:
            rule_class = CallClassification.SPAM.value
        elif signals.get("cancellation_tool"):
            rule_class = CallClassification.CANCELLATION.value
        elif signals.get("booking_tool"):
            rule_class = CallClassification.BOOKING.value

        result = self._provider.analyze(
            transcript_text=transcript.full_text,
            call_signals=signals,
        )
        payload = dict(result.payload)
        payload["appointment_status"] = appt_status

        if rule_class:
            payload["classification"] = rule_class
            if rule_class in {e.value for e in CallIntent}:
                payload["intent"] = rule_class
            payload["classification_source"] = (
                ClassificationSource.HYBRID.value
                if payload.get("classification_source") == ClassificationSource.AI.value
                else ClassificationSource.RULE.value
            )
            payload["classification_confidence"] = max(
                float(payload.get("classification_confidence") or 0), 0.95
            )

        row.intent = payload["intent"]
        row.problem = payload["problem"]
        row.outcome = payload["outcome"]
        row.sentiment = payload["sentiment"]
        row.appointment_status = payload["appointment_status"]
        row.follow_up = payload["follow_up"]
        row.classification = payload["classification"]
        row.classification_confidence = payload["classification_confidence"]
        row.classification_source = payload["classification_source"]
        row.important_notes = payload["important_notes"]
        row.provider = result.provider
        row.model = result.model
        row.model_version = result.model_version
        row.analysis_status = ProcessingStatus.COMPLETED.value
        row.completed_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return serialize_intelligence(row)

    def cleanup_expired(self, *, limit: int = 100) -> int:
        now = datetime.now(UTC)
        rows = list(
            self._session.scalars(
                select(CallIntelligence)
                .where(
                    CallIntelligence.lifecycle_status == LifecycleStatus.ACTIVE.value,
                    CallIntelligence.expires_at.is_not(None),
                    CallIntelligence.expires_at <= now,
                    CallIntelligence.deleted_at.is_(None),
                )
                .limit(limit)
            ).all()
        )
        for row in rows:
            row.lifecycle_status = LifecycleStatus.EXPIRED.value
            row.updated_at = now
        self._session.flush()

        expired = list(
            self._session.scalars(
                select(CallIntelligence)
                .where(
                    CallIntelligence.lifecycle_status == LifecycleStatus.EXPIRED.value,
                    CallIntelligence.deleted_at.is_(None),
                )
                .limit(limit)
            ).all()
        )
        for row in expired:
            row.problem = None
            row.outcome = None
            row.important_notes = []
            row.lifecycle_status = LifecycleStatus.DELETED.value
            row.deleted_at = now
            row.updated_at = now
        self._session.flush()
        return len(expired)
