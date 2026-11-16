"""Webhook ingestion — verify, persist, dedupe, process async."""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.integrations import (
    IntegrationConnection,
    IntegrationWebhookEvent,
)
from callbot_platform.integrations.errors import WebhookInvalidError
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


def payload_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def verify_hmac_sha256(
    *,
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
    prefix: str = "sha256=",
) -> bool:
    if not signature_header or not secret:
        return False
    provided = signature_header.strip()
    if provided.startswith(prefix):
        provided = provided[len(prefix) :]
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, expected)


class WebhookIngestService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ingest(
        self,
        *,
        tenant_id: UUID,
        integration_id: UUID,
        provider_event_id: str,
        event_type: str,
        raw_body: bytes,
        actor: str = "webhook",
    ) -> dict[str, Any]:
        conn = self._session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.tenant_id == tenant_id,
                IntegrationConnection.id == integration_id,
            )
        )
        if conn is None:
            raise WebhookInvalidError("Unknown integration for webhook")

        existing = self._session.scalar(
            select(IntegrationWebhookEvent).where(
                IntegrationWebhookEvent.tenant_id == tenant_id,
                IntegrationWebhookEvent.integration_id == integration_id,
                IntegrationWebhookEvent.provider_event_id == provider_event_id,
            )
        )
        if existing is not None:
            existing.status = "DUPLICATE"
            self._session.flush()
            return {
                "id": str(existing.id),
                "status": "DUPLICATE",
                "duplicate": True,
            }

        row = IntegrationWebhookEvent(
            tenant_id=tenant_id,
            integration_id=integration_id,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload_hash=payload_hash(raw_body),
            status="RECEIVED",
        )
        self._session.add(row)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="integration_webhook_received",
            resource_ids={
                "integration_id": str(integration_id),
                "provider": conn.provider,
                "provider_event_id": provider_event_id,
            },
            payload_summary={"event_type": event_type},
        )
        self._session.flush()
        logger.info(
            "integration_webhook_received tenant_id=%s integration_id=%s "
            "provider=%s event_type=%s",
            tenant_id,
            integration_id,
            conn.provider,
            event_type,
        )
        return {"id": str(row.id), "status": row.status, "duplicate": False}

    def mark_processed(
        self, *, tenant_id: UUID, event_id: UUID, error: str | None = None
    ) -> None:
        row = self._session.scalar(
            select(IntegrationWebhookEvent).where(
                IntegrationWebhookEvent.tenant_id == tenant_id,
                IntegrationWebhookEvent.id == event_id,
            )
        )
        if row is None:
            return
        row.attempt_count += 1
        if error:
            row.status = "FAILED"
            row.last_error = error[:500]
        else:
            row.status = "PROCESSED"
            row.processed_at = datetime.now(UTC)
            row.last_error = None
        self._session.flush()
