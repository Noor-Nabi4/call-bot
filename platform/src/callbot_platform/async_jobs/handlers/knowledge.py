"""Async job handler for knowledge ingestion / reindex."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.config import Settings
from callbot_platform.db.models.async_job import AsyncJob
from callbot_platform.knowledge.ingestion import KnowledgeIngestionPipeline
from callbot_platform.knowledge.repos import KnowledgeError


class KnowledgeIngestHandler:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def handle(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        payload = dict(job.payload or {})
        source_id = UUID(str(payload["source_id"]))
        version = int(payload.get("version") or 1)
        inline_text = payload.get("inline_text")
        try:
            return KnowledgeIngestionPipeline(
                session, settings=self._settings
            ).process_source(
                job.tenant_id,
                source_id,
                version=version,
                inline_text=inline_text if isinstance(inline_text, str) else None,
            )
        except KnowledgeError as exc:
            # Permanent document errors should not infinite-retry.
            if exc.code in {
                "invalid_document",
                "invalid_source",
                "invalid_type",
                "ssrf_blocked",
                "invalid_url",
            }:
                return {
                    "status": "FAILED",
                    "code": exc.code,
                    "message": str(exc)[:500],
                    "permanent": True,
                }
            raise
