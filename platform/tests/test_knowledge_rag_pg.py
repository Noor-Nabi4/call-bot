"""PostgreSQL + pgvector checks for Phase 16 knowledge RAG."""

from __future__ import annotations

import os
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.db.models import Base, Tenant
from callbot_platform.knowledge.embeddings import FakeEmbeddingService
from callbot_platform.knowledge.ingestion import KnowledgeIngestionPipeline
from callbot_platform.knowledge.retrieval import KnowledgeRetrievalService
from callbot_platform.knowledge.sources import KnowledgeSourceService
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

PG_URL = os.environ.get(
    "KNOWLEDGE_PG_TEST_URL",
    os.environ.get(
        "AI_TOOLS_PG_TEST_URL",
        "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
    ),
)


def _pg_available(url: str) -> bool:
    try:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        return False
    return True


_PG_UP = _pg_available(PG_URL)

pytestmark = pytest.mark.skipif(
    not _PG_UP, reason="PostgreSQL not available for knowledge RAG PG tests"
)


@pytest.fixture()
def pg_factory():
    engine = create_engine(PG_URL, future=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    # Ensure vector column exists for ANN (Alembic does this in real deploys).
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $$ BEGIN
                  ALTER TABLE knowledge_chunks
                    ADD COLUMN IF NOT EXISTS embedding_vec vector(64);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
                """
            )
        )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def test_pg_vector_retrieval_and_explain(pg_factory) -> None:
    emb = FakeEmbeddingService(dimension=64, model="fake-test", version="v1")
    session: Session = pg_factory()
    try:
        tenant = Tenant(name="KB PG", slug=f"kb-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        ensure_system_roles_for_tenant(session, tenant.id)
        text_body = (
            "Return policy: unused items may be returned within thirty days "
            "with receipt for a full refund."
        )
        src = KnowledgeSourceService(session).create_text(
            tenant.id,
            name="Returns",
            text=text_body,
            source_type="POLICY",
            actor="test",
            sync=False,
        )
        KnowledgeIngestionPipeline(session, embeddings=emb).process_source(
            tenant.id,
            uuid.UUID(src["id"]),
            version=1,
            inline_text=text_body,
        )
        session.commit()
        tenant_id = tenant.id
    finally:
        session.close()

    s = pg_factory()
    try:
        started = time.perf_counter()
        result = KnowledgeRetrievalService(s, embeddings=emb).retrieve(
            tenant_id,
            "return policy refund",
            top_k=5,
            relevance_threshold=0.1,
            include_legacy_articles=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        assert result["status"] == "OK"
        assert result["count"] >= 1
        plan = s.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM knowledge_chunks
                WHERE tenant_id = :tid AND is_active = true
                LIMIT 20
                """
            ),
            {"tid": str(tenant_id)},
        ).fetchall()
        plan_text = "\n".join(r[0] for r in plan)
        print(f"\nKNOWLEDGE_PG retrieval_ms={elapsed_ms:.2f}\n{plan_text}\n")
        assert "knowledge_chunks" in plan_text
    finally:
        s.close()
