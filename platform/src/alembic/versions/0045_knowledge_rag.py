"""Phase 16 Knowledge Base RAG: sources, versions, chunks, pgvector."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0045_knowledge_rag"
down_revision = "0044_sms_agent"
branch_labels = None
depends_on = None

# OpenAI text-embedding-3-small default dimension
EMBED_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PROCESSING"),
        sa.Column("source_uri", sa.String(2048), nullable=True),
        sa.Column("object_key", sa.String(512), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active_version", sa.Integer(), nullable=True),
        sa.Column("embedding_model", sa.String(128), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("embedding_version", sa.String(64), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_message", sa.String(500), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ("
            "'PDF','DOCX','WEBSITE','TEXT','FAQ','POLICY',"
            "'BUSINESS_INFORMATION','PRODUCT_DESCRIPTION'"
            ")",
            name="ck_knowledge_sources_type",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','PROCESSING','FAILED','ARCHIVED','DELETED')",
            name="ck_knowledge_sources_status",
        ),
    )
    op.create_index(
        "ix_knowledge_sources_tenant_status",
        "knowledge_sources",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_knowledge_sources_tenant_type",
        "knowledge_sources",
        ["tenant_id", "source_type"],
    )
    op.create_index(
        "ix_knowledge_sources_tenant_updated",
        "knowledge_sources",
        ["tenant_id", "updated_at"],
    )
    op.create_index(
        "ix_knowledge_sources_tenant_hash",
        "knowledge_sources",
        ["tenant_id", "content_hash", "embedding_version"],
    )

    op.create_table(
        "knowledge_source_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PROCESSING"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("embedding_model", sa.String(128), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("embedding_version", sa.String(64), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PROCESSING','ACTIVE','FAILED','SUPERSEDED')",
            name="ck_knowledge_source_versions_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "source_id",
            "version",
            name="uq_knowledge_source_versions_src_ver",
        ),
    )
    op.create_index(
        "ix_knowledge_source_versions_tenant_source",
        "knowledge_source_versions",
        ["tenant_id", "source_id", "version"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "embedding_vec",
            sa.Text(),
            nullable=True,
        ),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("embedding_version", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(255), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "source_id",
            "source_version",
            "chunk_index",
            name="uq_knowledge_chunks_src_ver_idx",
        ),
    )
    # Replace text placeholder with real vector type.
    op.execute(
        f"ALTER TABLE knowledge_chunks ALTER COLUMN embedding_vec "
        f"TYPE vector({EMBED_DIM}) USING NULL"
    )
    op.create_index(
        "ix_knowledge_chunks_tenant_active",
        "knowledge_chunks",
        ["tenant_id", "is_active", "source_id"],
    )
    op.create_index(
        "ix_knowledge_chunks_tenant_source_version",
        "knowledge_chunks",
        ["tenant_id", "source_id", "source_version"],
    )
    op.create_index(
        "ix_knowledge_chunks_tenant_type",
        "knowledge_chunks",
        ["tenant_id", "source_type"],
    )
    # HNSW cosine index — requires rows before meaningful planner use.
    op.execute(
        """
        CREATE INDEX ix_knowledge_chunks_embedding_hnsw
        ON knowledge_chunks
        USING hnsw (embedding_vec vector_cosine_ops)
        WHERE is_active = true AND embedding_vec IS NOT NULL
        """
    )

    op.create_table(
        "knowledge_retrieval_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "source_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "scores",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_knowledge_retrieval_logs_tenant_created",
        "knowledge_retrieval_logs",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_retrieval_logs_tenant_created",
        table_name="knowledge_retrieval_logs",
    )
    op.drop_table("knowledge_retrieval_logs")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.drop_index("ix_knowledge_chunks_tenant_type", table_name="knowledge_chunks")
    op.drop_index(
        "ix_knowledge_chunks_tenant_source_version", table_name="knowledge_chunks"
    )
    op.drop_index("ix_knowledge_chunks_tenant_active", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index(
        "ix_knowledge_source_versions_tenant_source",
        table_name="knowledge_source_versions",
    )
    op.drop_table("knowledge_source_versions")
    op.drop_index("ix_knowledge_sources_tenant_hash", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_tenant_updated", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_tenant_type", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_tenant_status", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
