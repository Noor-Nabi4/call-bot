"""Knowledge ingestion pipeline: extract → chunk → embed → store."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.knowledge_rag import (
    KnowledgeChunk,
    KnowledgeSource,
    KnowledgeSourceVersion,
)
from callbot_platform.knowledge.chunking import chunk_text
from callbot_platform.knowledge.embeddings import (
    EmbeddingService,
    get_embedding_service,
)
from callbot_platform.knowledge.extractors import DocumentExtractor
from callbot_platform.knowledge.repos import KnowledgeError
from callbot_platform.storage import get_object_storage
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class KnowledgeIngestionPipeline:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._embeddings = embeddings or get_embedding_service(self._settings)
        self._extractor = DocumentExtractor()
        self._storage = get_object_storage(self._settings)

    def process_source(
        self,
        tenant_id: UUID,
        source_id: UUID,
        *,
        version: int | None = None,
        inline_text: str | None = None,
    ) -> dict[str, Any]:
        source = self._session.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.tenant_id == tenant_id,
                KnowledgeSource.id == source_id,
            )
        )
        if source is None:
            raise KnowledgeError("not_found", "Knowledge source not found")
        ver = int(version or source.version or 1)

        # Version row — preserve prior ACTIVE on failure.
        ver_row = self._session.scalar(
            select(KnowledgeSourceVersion).where(
                KnowledgeSourceVersion.tenant_id == tenant_id,
                KnowledgeSourceVersion.source_id == source_id,
                KnowledgeSourceVersion.version == ver,
            )
        )
        if ver_row is None:
            ver_row = KnowledgeSourceVersion(
                tenant_id=tenant_id,
                source_id=source_id,
                version=ver,
                status="PROCESSING",
                content_hash=source.content_hash,
                embedding_model=self._embeddings.model,
                embedding_dimension=self._embeddings.dimension,
                embedding_version=self._embeddings.version,
            )
            self._session.add(ver_row)
            self._session.flush()
        elif ver_row.status == "ACTIVE":
            return {"status": "ACTIVE", "source_id": str(source_id), "version": ver}

        try:
            extracted = self._load_extracted(source, inline_text=inline_text)
            chunks = chunk_text(extracted.text)
            if not chunks:
                raise KnowledgeError("invalid_document", "No chunks produced")

            texts = [c.text for c in chunks]
            vectors = self._embeddings.generate_batch(texts)
            if len(vectors) != len(chunks):
                raise KnowledgeError("invalid_embedding", "Embedding count mismatch")

            # Remove any prior chunks for this version (retry-safe).
            old = self._session.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.tenant_id == tenant_id,
                    KnowledgeChunk.source_id == source_id,
                    KnowledgeChunk.source_version == ver,
                )
            ).all()
            for row in old:
                self._session.delete(row)
            self._session.flush()

            category = (source.metadata_json or {}).get("category")
            for chunk, vec in zip(chunks, vectors, strict=True):
                if len(vec) != self._embeddings.dimension:
                    raise KnowledgeError("invalid_embedding", "Dimension mismatch")
                row = KnowledgeChunk(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    source_version=ver,
                    chunk_index=chunk.chunk_index,
                    content=chunk.text,
                    embedding=vec,
                    embedding_model=self._embeddings.model,
                    embedding_dimension=self._embeddings.dimension,
                    embedding_version=self._embeddings.version,
                    source_type=source.source_type,
                    title=extracted.title or source.name,
                    category=str(category) if category else None,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    url=(extracted.metadata or {}).get("url") or source.source_uri,
                    is_active=False,  # activated with version
                    metadata_json={
                        "source_name": source.name,
                        "untrusted": True,
                    },
                )
                self._session.add(row)
            self._session.flush()

            # Sync PG vector column when available.
            self._sync_pg_vectors(tenant_id, source_id, ver)

            # Activate version atomically: deactivate other versions' chunks.
            self._session.execute(
                update(KnowledgeChunk)
                .where(
                    KnowledgeChunk.tenant_id == tenant_id,
                    KnowledgeChunk.source_id == source_id,
                    KnowledgeChunk.source_version != ver,
                )
                .values(is_active=False)
            )
            self._session.execute(
                update(KnowledgeChunk)
                .where(
                    KnowledgeChunk.tenant_id == tenant_id,
                    KnowledgeChunk.source_id == source_id,
                    KnowledgeChunk.source_version == ver,
                )
                .values(is_active=True)
            )
            prior_versions = self._session.scalars(
                select(KnowledgeSourceVersion).where(
                    KnowledgeSourceVersion.tenant_id == tenant_id,
                    KnowledgeSourceVersion.source_id == source_id,
                    KnowledgeSourceVersion.version != ver,
                    KnowledgeSourceVersion.status == "ACTIVE",
                )
            ).all()
            for pv in prior_versions:
                pv.status = "SUPERSEDED"

            now = datetime.now(UTC)
            ver_row.status = "ACTIVE"
            ver_row.chunk_count = len(chunks)
            ver_row.embedding_model = self._embeddings.model
            ver_row.embedding_dimension = self._embeddings.dimension
            ver_row.embedding_version = self._embeddings.version
            ver_row.content_hash = source.content_hash
            ver_row.activated_at = now
            ver_row.failure_code = None
            ver_row.failure_message = None

            source.status = "ACTIVE"
            source.active_version = ver
            source.version = ver
            source.chunk_count = len(chunks)
            source.embedding_model = self._embeddings.model
            source.embedding_dimension = self._embeddings.dimension
            source.embedding_version = self._embeddings.version
            source.last_indexed_at = now
            source.failure_code = None
            source.failure_message = None
            source.updated_at = now
            if extracted.title and not source.name:
                source.name = extracted.title[:255]
            self._session.flush()

            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor="system",
                action="knowledge.ingestion.completed",
                resource_ids={
                    "source_id": str(source_id),
                    "version": ver,
                    "chunk_count": len(chunks),
                },
                idempotency_key=f"knowledge_ingest_done:{source_id}:{ver}",
            )
            logger.info(
                "knowledge_ingestion_success tenant_id=%s source_id=%s chunks=%s",
                tenant_id,
                source_id,
                len(chunks),
            )
            return {
                "status": "ACTIVE",
                "source_id": str(source_id),
                "version": ver,
                "chunk_count": len(chunks),
            }
        except KnowledgeError as exc:
            self._mark_failed(source, ver_row, code=exc.code, message=str(exc)[:500])
            raise
        except Exception as exc:
            logger.exception(
                "knowledge_ingestion_failure tenant_id=%s source_id=%s",
                tenant_id,
                source_id,
            )
            self._mark_failed(
                source, ver_row, code="ingestion_failed", message=type(exc).__name__
            )
            raise KnowledgeError("ingestion_failed", "Knowledge ingestion failed") from exc

    def _mark_failed(
        self,
        source: KnowledgeSource,
        ver_row: KnowledgeSourceVersion,
        *,
        code: str,
        message: str,
    ) -> None:
        ver_row.status = "FAILED"
        ver_row.failure_code = code
        ver_row.failure_message = message
        # Keep prior ACTIVE source usable when reindex fails.
        if source.active_version is not None and source.active_version != ver_row.version:
            source.status = "ACTIVE"
        else:
            source.status = "FAILED"
        source.failure_code = code
        source.failure_message = message
        source.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=source.tenant_id,
            actor="system",
            action="knowledge.ingestion.failed",
            resource_ids={
                "source_id": str(source.id),
                "version": ver_row.version,
                "code": code,
            },
        )
        logger.info(
            "knowledge_ingestion_failure tenant_id=%s source_id=%s code=%s",
            source.tenant_id,
            source.id,
            code,
        )

    def _load_extracted(
        self, source: KnowledgeSource, *, inline_text: str | None
    ):
        if inline_text is not None:
            return self._extractor.extract_text(
                inline_text, source_type=source.source_type, title=source.name
            )
        if source.source_type == "WEBSITE":
            if not source.source_uri:
                raise KnowledgeError("invalid_source", "Website URL missing")
            return self._extractor.extract_url(source.source_uri)
        if source.object_key:
            data = self._storage.get(
                tenant_id=source.tenant_id, object_key=source.object_key
            )
            return self._extractor.extract_bytes(
                data,
                source_type=source.source_type,
                filename=source.source_uri or source.name,
            )
        raise KnowledgeError("invalid_source", "No content available for extraction")

    def _sync_pg_vectors(
        self, tenant_id: UUID, source_id: UUID, version: int
    ) -> None:
        bind = self._session.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            return
        rows = self._session.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.tenant_id == tenant_id,
                KnowledgeChunk.source_id == source_id,
                KnowledgeChunk.source_version == version,
            )
        ).all()
        for row in rows:
            if not row.embedding:
                continue
            vec_literal = "[" + ",".join(str(float(x)) for x in row.embedding) + "]"
            try:
                self._session.execute(
                    text(
                        "UPDATE knowledge_chunks SET embedding_vec = CAST(:v AS vector) "
                        "WHERE id = :id AND tenant_id = :tid"
                    ),
                    {"v": vec_literal, "id": str(row.id), "tid": str(tenant_id)},
                )
            except Exception:
                logger.warning(
                    "knowledge_pg_vector_sync_failed chunk_id=%s",
                    row.id,
                    exc_info=True,
                )
