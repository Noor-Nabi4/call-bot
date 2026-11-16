"""Knowledge source CRUD, upload, reindex, delete."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.async_jobs.service import AsyncJobService
from callbot_platform.async_jobs.types import JobType
from callbot_platform.billing.entitlements import EntitlementError, EntitlementGuard
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.knowledge_rag import KnowledgeChunk, KnowledgeSource
from callbot_platform.knowledge.constants import (
    ALLOWED_UPLOAD_MIME,
    DOCX_MAGIC,
    MAX_UPLOAD_BYTES,
    PDF_MAGIC,
    SOURCE_TYPES,
)
from callbot_platform.knowledge.metadata import normalize_metadata
from callbot_platform.knowledge.repos import KnowledgeError
from callbot_platform.knowledge.ssrf import validate_public_http_url
from callbot_platform.storage import get_object_storage
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class KnowledgeSourceService:
    def __init__(
        self, session: Session, *, settings: Settings | None = None
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._jobs = AsyncJobService(session, settings=self._settings)
        self._storage = get_object_storage(self._settings)

    def list(
        self,
        tenant_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]:
        q = select(KnowledgeSource).where(
            KnowledgeSource.tenant_id == tenant_id,
            KnowledgeSource.status != "DELETED",
        )
        if status:
            q = q.where(KnowledgeSource.status == status.upper())
        if source_type:
            q = q.where(KnowledgeSource.source_type == source_type.upper())
        rows = self._session.scalars(
            q.order_by(KnowledgeSource.updated_at.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 200)))
        ).all()
        return [self.serialize(r) for r in rows]

    def get(self, tenant_id: UUID, source_id: UUID) -> dict[str, Any]:
        return self.serialize(self._get(tenant_id, source_id))

    def create_text(
        self,
        tenant_id: UUID,
        *,
        name: str,
        text: str,
        source_type: str = "TEXT",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        product_id: UUID | None = None,
        actor: str = "ops",
        sync: bool = False,
    ) -> dict[str, Any]:
        st = source_type.upper()
        if st not in SOURCE_TYPES:
            raise KnowledgeError("invalid_type", f"Unsupported source type: {st}")
        if st in {"PDF", "DOCX", "WEBSITE"}:
            raise KnowledgeError("invalid_type", f"Use dedicated create for {st}")
        body = (text or "").strip()
        title = (name or "").strip()
        if not title or not body:
            raise KnowledgeError("invalid_source", "name and text are required")
        meta = normalize_metadata(metadata)
        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return self._create_and_enqueue(
            tenant_id,
            source_type=st,
            name=title[:255],
            description=description,
            content_hash=content_hash,
            source_uri=None,
            object_key=None,
            mime_type="text/plain",
            metadata=meta,
            product_id=product_id,
            inline_text=body,
            actor=actor,
            sync=sync,
        )

    def create_website(
        self,
        tenant_id: UUID,
        *,
        name: str,
        url: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor: str = "ops",
        sync: bool = False,
    ) -> dict[str, Any]:
        safe_url = validate_public_http_url(url)
        title = (name or "").strip() or safe_url[:255]
        meta = normalize_metadata(metadata)
        content_hash = hashlib.sha256(safe_url.encode("utf-8")).hexdigest()
        return self._create_and_enqueue(
            tenant_id,
            source_type="WEBSITE",
            name=title[:255],
            description=description,
            content_hash=content_hash,
            source_uri=safe_url,
            object_key=None,
            mime_type="text/html",
            metadata=meta,
            product_id=None,
            inline_text=None,
            actor=actor,
            sync=sync,
        )

    def create_upload(
        self,
        tenant_id: UUID,
        *,
        name: str,
        filename: str,
        data: bytes,
        source_type: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor: str = "ops",
        sync: bool = False,
    ) -> dict[str, Any]:
        st = source_type.upper()
        if st not in {"PDF", "DOCX"}:
            raise KnowledgeError("invalid_type", "Upload supports PDF or DOCX")
        if not data:
            raise KnowledgeError("invalid_document", "Empty upload")
        if len(data) > MAX_UPLOAD_BYTES:
            raise KnowledgeError("invalid_document", "File exceeds size limit")
        if st == "PDF" and not data.startswith(PDF_MAGIC):
            raise KnowledgeError("invalid_document", "Invalid PDF signature")
        if st == "DOCX" and not data.startswith(DOCX_MAGIC):
            raise KnowledgeError("invalid_document", "Invalid DOCX signature")
        mime = self._detect_mime(st, data, filename)
        if mime not in ALLOWED_UPLOAD_MIME:
            raise KnowledgeError("invalid_document", f"Unsupported MIME type: {mime}")
        content_hash = hashlib.sha256(data).hexdigest()
        object_key = f"knowledge/{content_hash[:16]}/{filename[:120]}"
        self._storage.put(
            tenant_id=tenant_id,
            object_key=object_key,
            data=data,
            mime_type=mime,
        )
        meta = normalize_metadata(metadata)
        return self._create_and_enqueue(
            tenant_id,
            source_type=st,
            name=(name or filename).strip()[:255],
            description=description,
            content_hash=content_hash,
            source_uri=filename,
            object_key=object_key,
            mime_type=mime,
            metadata=meta,
            product_id=None,
            inline_text=None,
            actor=actor,
            sync=sync,
        )

    def reindex(
        self,
        tenant_id: UUID,
        source_id: UUID,
        *,
        actor: str = "ops",
        sync: bool = False,
    ) -> dict[str, Any]:
        row = self._get(tenant_id, source_id)
        if row.status == "DELETED":
            raise KnowledgeError("not_found", "Source not found")
        row.status = "PROCESSING"
        row.version = int(row.version or 1) + 1
        row.failure_code = None
        row.failure_message = None
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="knowledge.source.reindexed",
            resource_ids={"source_id": str(row.id), "version": row.version},
        )
        self._enqueue(row, inline_text=None, sync=sync)
        return self.serialize(row)

    def delete(
        self, tenant_id: UUID, source_id: UUID, *, actor: str = "ops"
    ) -> None:
        row = self._get(tenant_id, source_id)
        row.status = "DELETED"
        row.updated_at = datetime.now(UTC)
        chunks = self._session.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.tenant_id == tenant_id,
                KnowledgeChunk.source_id == source_id,
                KnowledgeChunk.is_active.is_(True),
            )
        ).all()
        for chunk in chunks:
            chunk.is_active = False
        self._session.flush()
        if row.object_key:
            try:
                self._storage.delete(tenant_id=tenant_id, object_key=row.object_key)
            except Exception:
                logger.warning(
                    "knowledge_object_delete_failed source_id=%s", row.id, exc_info=True
                )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="knowledge.source.deleted",
            resource_ids={"source_id": str(row.id)},
        )

    def serialize(self, row: KnowledgeSource) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "source_type": row.source_type,
            "name": row.name,
            "description": row.description,
            "status": row.status,
            "source_uri": row.source_uri,
            "mime_type": row.mime_type,
            "content_hash": row.content_hash,
            "version": row.version,
            "active_version": row.active_version,
            "embedding_model": row.embedding_model,
            "embedding_dimension": row.embedding_dimension,
            "embedding_version": row.embedding_version,
            "chunk_count": row.chunk_count,
            "failure_code": row.failure_code,
            "failure_message": row.failure_message,
            "metadata": row.metadata_json or {},
            "product_id": str(row.product_id) if row.product_id else None,
            "last_indexed_at": row.last_indexed_at.isoformat()
            if row.last_indexed_at
            else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _create_and_enqueue(
        self,
        tenant_id: UUID,
        *,
        source_type: str,
        name: str,
        description: str | None,
        content_hash: str,
        source_uri: str | None,
        object_key: str | None,
        mime_type: str | None,
        metadata: dict[str, Any],
        product_id: UUID | None,
        inline_text: str | None,
        actor: str,
        sync: bool,
    ) -> dict[str, Any]:
        try:
            EntitlementGuard(self._session).require_capacity(
                tenant_id, "knowledge_documents"
            )
        except EntitlementError as exc:
            raise KnowledgeError(exc.code, str(exc)) from exc

        emb_ver = self._settings.knowledge_embedding_version
        # Idempotent: same tenant+hash+embedding_version ACTIVE/PROCESSING → reuse.
        existing = self._session.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.tenant_id == tenant_id,
                KnowledgeSource.content_hash == content_hash,
                KnowledgeSource.embedding_version == emb_ver,
                KnowledgeSource.status.in_(["ACTIVE", "PROCESSING"]),
            )
        )
        if existing is not None:
            return self.serialize(existing)

        row = KnowledgeSource(
            tenant_id=tenant_id,
            source_type=source_type,
            name=name,
            description=(description or None),
            status="PROCESSING",
            source_uri=source_uri,
            object_key=object_key,
            mime_type=mime_type,
            content_hash=content_hash,
            version=1,
            embedding_version=emb_ver,
            metadata_json=metadata,
            product_id=product_id,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="knowledge.source.created",
            resource_ids={"source_id": str(row.id), "source_type": source_type},
        )
        self._enqueue(row, inline_text=inline_text, sync=sync)
        return self.serialize(row)

    def _enqueue(
        self,
        row: KnowledgeSource,
        *,
        inline_text: str | None,
        sync: bool,
    ) -> None:
        payload = {
            "source_id": str(row.id),
            "version": row.version,
            "inline_text": inline_text,
        }
        job = self._jobs.enqueue(
            tenant_id=row.tenant_id,
            job_type=JobType.KNOWLEDGE_INGEST,
            idempotency_key=f"knowledge_ingest:{row.id}:{row.version}",
            resource_id=str(row.id),
            payload=payload,
        )
        logger.info(
            "knowledge_ingestion_started tenant_id=%s source_id=%s job_id=%s",
            row.tenant_id,
            row.id,
            job.id,
        )
        write_audit(
            self._session,
            tenant_id=row.tenant_id,
            actor="system",
            action="knowledge.ingestion.started",
            resource_ids={
                "source_id": str(row.id),
                "job_id": str(job.id),
                "version": row.version,
            },
            idempotency_key=f"knowledge_ingest_start:{row.id}:{row.version}",
        )
        if sync:
            from callbot_platform.knowledge.ingestion import KnowledgeIngestionPipeline

            KnowledgeIngestionPipeline(
                self._session, settings=self._settings
            ).process_source(row.tenant_id, row.id, version=row.version, inline_text=inline_text)

    def _get(self, tenant_id: UUID, source_id: UUID) -> KnowledgeSource:
        row = self._session.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.tenant_id == tenant_id,
                KnowledgeSource.id == source_id,
            )
        )
        if row is None or row.status == "DELETED":
            raise KnowledgeError("not_found", "Knowledge source not found")
        return row

    @staticmethod
    def _detect_mime(source_type: str, data: bytes, filename: str) -> str:
        if source_type == "PDF" or data.startswith(PDF_MAGIC):
            return "application/pdf"
        if source_type == "DOCX" or (
            data.startswith(DOCX_MAGIC) and filename.lower().endswith(".docx")
        ):
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return "application/octet-stream"
