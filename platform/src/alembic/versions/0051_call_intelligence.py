"""Phase 23 Call Intelligence: recordings enrichment, transcripts, analysis."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0051_call_intelligence"
down_revision = "0050_automations"
branch_labels = None
depends_on = None

_EVENT_TYPES = (
    "CALL_COMPLETED",
    "CALL_TRANSCRIBED",
    "CALL_ANALYZED",
    "CALL_CLASSIFIED",
    "LEAD_CREATED",
    "JOB_CREATED",
    "APPOINTMENT_CREATED",
    "APPOINTMENT_REMINDER",
    "TECHNICIAN_DISPATCHED",
    "JOB_COMPLETED",
    "ESTIMATE_SENT",
    "ESTIMATE_APPROVED",
    "INVOICE_CREATED",
    "PAYMENT_COMPLETED",
    "ORDER_CREATED",
    "ORDER_SHIPPED",
)

_EVENT_TYPES_PREV = (
    "CALL_COMPLETED",
    "LEAD_CREATED",
    "JOB_CREATED",
    "APPOINTMENT_CREATED",
    "APPOINTMENT_REMINDER",
    "TECHNICIAN_DISPATCHED",
    "JOB_COMPLETED",
    "ESTIMATE_SENT",
    "ESTIMATE_APPROVED",
    "INVOICE_CREATED",
    "PAYMENT_COMPLETED",
    "ORDER_CREATED",
    "ORDER_SHIPPED",
)


def upgrade() -> None:
    # --- recording_objects enrichment ---
    op.add_column(
        "recording_objects",
        sa.Column("provider", sa.String(64), nullable=False, server_default="internal"),
    )
    op.add_column(
        "recording_objects",
        sa.Column("provider_recording_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "recording_objects",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "recording_objects",
        sa.Column("checksum", sa.String(128), nullable=True),
    )
    op.add_column(
        "recording_objects",
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "recording_objects",
        sa.Column(
            "lifecycle_status",
            sa.String(32),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.create_check_constraint(
        "ck_recording_objects_lifecycle",
        "recording_objects",
        "lifecycle_status IN ('ACTIVE','EXPIRED','DELETED')",
    )
    op.create_check_constraint(
        "ck_recording_objects_status",
        "recording_objects",
        "status IN ("
        "'PENDING','AVAILABLE','PROCESSING','READY','FAILED','DELETED','EXPIRED',"
        "'stored','delete_failed'"
        ")",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_recording_objects_tenant_provider_rec
        ON recording_objects (tenant_id, provider, provider_recording_id)
        WHERE provider_recording_id IS NOT NULL
        """
    )
    op.create_index(
        "ix_recording_objects_tenant_call",
        "recording_objects",
        ["tenant_id", "call_id"],
    )
    op.create_index(
        "ix_recording_objects_tenant_lifecycle",
        "recording_objects",
        ["tenant_id", "lifecycle_status"],
    )

    # --- tenant retention flags ---
    op.add_column(
        "tenant_retention_settings",
        sa.Column(
            "recording_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "tenant_retention_settings",
        sa.Column(
            "transcription_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "tenant_retention_settings",
        sa.Column(
            "analysis_retention_days",
            sa.Integer(),
            nullable=False,
            server_default="90",
        ),
    )

    # --- call_transcripts ---
    op.create_table(
        "call_transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recording_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recording_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(64), nullable=False, server_default="internal"),
        sa.Column("provider_transcript_id", sa.String(255), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("full_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.String(32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING','PROCESSING','COMPLETED','FAILED')",
            name="ck_call_transcripts_status",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('ACTIVE','EXPIRED','DELETED')",
            name="ck_call_transcripts_lifecycle",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_call_transcripts_attempts",
        ),
    )
    op.create_index(
        "ix_call_transcripts_tenant_call",
        "call_transcripts",
        ["tenant_id", "call_id"],
    )
    op.create_index(
        "ix_call_transcripts_tenant_status",
        "call_transcripts",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_call_transcripts_tenant_created",
        "call_transcripts",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_call_transcripts_tenant_lifecycle",
        "call_transcripts",
        ["tenant_id", "lifecycle_status"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_call_transcripts_tenant_recording
        ON call_transcripts (tenant_id, recording_id)
        WHERE recording_id IS NOT NULL AND deleted_at IS NULL
          AND status IN ('PENDING','PROCESSING','COMPLETED')
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_call_transcripts_tenant_provider_tx
        ON call_transcripts (tenant_id, provider, provider_transcript_id)
        WHERE provider_transcript_id IS NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE call_transcripts
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
          to_tsvector('english', coalesce(full_text, ''))
        ) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_call_transcripts_search_vector
        ON call_transcripts USING GIN (search_vector)
        """
    )

    # --- call_transcript_segments ---
    op.create_table(
        "call_transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transcript_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("call_transcripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("speaker", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "speaker IN ('CUSTOMER','AGENT','SYSTEM','UNKNOWN')",
            name="ck_call_transcript_segments_speaker",
        ),
        sa.CheckConstraint(
            "start_ms >= 0 AND end_ms >= start_ms AND sequence >= 0",
            name="ck_call_transcript_segments_timing",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_call_transcript_segments_confidence",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "transcript_id",
            "sequence",
            name="uq_call_transcript_segments_seq",
        ),
    )
    op.create_index(
        "ix_call_transcript_segments_transcript_seq",
        "call_transcript_segments",
        ["transcript_id", "sequence"],
    )
    op.create_index(
        "ix_call_transcript_segments_tenant_speaker",
        "call_transcript_segments",
        ["tenant_id", "speaker"],
    )

    # --- call_intelligence ---
    op.create_table(
        "call_intelligence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transcript_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("call_transcripts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(32), nullable=True),
        sa.Column("appointment_status", sa.String(32), nullable=True),
        sa.Column("follow_up", sa.String(64), nullable=True),
        sa.Column("classification", sa.String(64), nullable=True),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("classification_source", sa.String(32), nullable=True),
        sa.Column(
            "important_notes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "analysis_status",
            sa.String(32),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.String(32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "analysis_status IN ('PENDING','PROCESSING','COMPLETED','FAILED')",
            name="ck_call_intelligence_status",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('ACTIVE','EXPIRED','DELETED')",
            name="ck_call_intelligence_lifecycle",
        ),
        sa.CheckConstraint(
            "sentiment IS NULL OR sentiment IN "
            "('POSITIVE','NEUTRAL','NEGATIVE','MIXED','UNKNOWN')",
            name="ck_call_intelligence_sentiment",
        ),
        sa.CheckConstraint(
            "intent IS NULL OR intent IN ("
            "'BOOKING','RESCHEDULING','CANCELLATION','SALES','SUPPORT',"
            "'EMERGENCY','BILLING','PRODUCT_INQUIRY','ORDER_INQUIRY',"
            "'SPAM','HUMAN_TRANSFER','OTHER'"
            ")",
            name="ck_call_intelligence_intent",
        ),
        sa.CheckConstraint(
            "classification IS NULL OR classification IN ("
            "'BOOKING','RESCHEDULING','CANCELLATION','SALES','SUPPORT',"
            "'EMERGENCY','BILLING','PRODUCT_INQUIRY','ORDER_INQUIRY',"
            "'SPAM','HUMAN_TRANSFER','OTHER'"
            ")",
            name="ck_call_intelligence_classification",
        ),
        sa.CheckConstraint(
            "follow_up IS NULL OR follow_up IN ("
            "'CALL_BACK','SEND_INFORMATION','SEND_PAYMENT_LINK',"
            "'FOLLOW_UP_SALES','TECHNICIAN_FOLLOW_UP',"
            "'CUSTOMER_ACTION_REQUIRED','NONE'"
            ")",
            name="ck_call_intelligence_follow_up",
        ),
        sa.CheckConstraint(
            "appointment_status IS NULL OR appointment_status IN ("
            "'NONE','REQUESTED','SCHEDULED','CONFIRMED','RESCHEDULED',"
            "'CANCELLED','COMPLETED','UNKNOWN'"
            ")",
            name="ck_call_intelligence_appt_status",
        ),
        sa.CheckConstraint(
            "classification_confidence IS NULL OR "
            "(classification_confidence >= 0 AND classification_confidence <= 1)",
            name="ck_call_intelligence_confidence",
        ),
        sa.CheckConstraint(
            "classification_source IS NULL OR "
            "classification_source IN ('RULE','AI','HYBRID')",
            name="ck_call_intelligence_class_source",
        ),
        sa.CheckConstraint(
            "analysis_version >= 1 AND attempt_count >= 0",
            name="ck_call_intelligence_versions",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "call_id",
            "analysis_version",
            name="uq_call_intelligence_tenant_call_version",
        ),
    )
    op.create_index(
        "ix_call_intelligence_tenant_call",
        "call_intelligence",
        ["tenant_id", "call_id"],
    )
    op.create_index(
        "ix_call_intelligence_tenant_created",
        "call_intelligence",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_call_intelligence_tenant_classification",
        "call_intelligence",
        ["tenant_id", "classification"],
    )
    op.create_index(
        "ix_call_intelligence_tenant_sentiment",
        "call_intelligence",
        ["tenant_id", "sentiment"],
    )
    op.create_index(
        "ix_call_intelligence_tenant_status",
        "call_intelligence",
        ["tenant_id", "analysis_status"],
    )
    op.create_index(
        "ix_call_intelligence_tenant_lifecycle",
        "call_intelligence",
        ["tenant_id", "lifecycle_status"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_call_intelligence_active_hash
        ON call_intelligence (tenant_id, call_id, input_hash)
        WHERE input_hash IS NOT NULL
          AND deleted_at IS NULL
          AND analysis_status IN ('PENDING','PROCESSING','COMPLETED')
        """
    )

    # --- automation event types ---
    op.drop_constraint(
        "ck_automation_events_type", "automation_events", type_="check"
    )
    event_enum = ", ".join(f"'{e}'" for e in _EVENT_TYPES)
    op.create_check_constraint(
        "ck_automation_events_type",
        "automation_events",
        f"event_type IN ({event_enum})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_automation_events_type", "automation_events", type_="check"
    )
    prev_enum = ", ".join(f"'{e}'" for e in _EVENT_TYPES_PREV)
    op.create_check_constraint(
        "ck_automation_events_type",
        "automation_events",
        f"event_type IN ({prev_enum})",
    )

    op.drop_index("uq_call_intelligence_active_hash", table_name="call_intelligence")
    op.drop_index(
        "ix_call_intelligence_tenant_lifecycle", table_name="call_intelligence"
    )
    op.drop_index("ix_call_intelligence_tenant_status", table_name="call_intelligence")
    op.drop_index(
        "ix_call_intelligence_tenant_sentiment", table_name="call_intelligence"
    )
    op.drop_index(
        "ix_call_intelligence_tenant_classification",
        table_name="call_intelligence",
    )
    op.drop_index(
        "ix_call_intelligence_tenant_created", table_name="call_intelligence"
    )
    op.drop_index("ix_call_intelligence_tenant_call", table_name="call_intelligence")
    op.drop_table("call_intelligence")

    op.drop_index(
        "ix_call_transcript_segments_tenant_speaker",
        table_name="call_transcript_segments",
    )
    op.drop_index(
        "ix_call_transcript_segments_transcript_seq",
        table_name="call_transcript_segments",
    )
    op.drop_table("call_transcript_segments")

    op.drop_index("ix_call_transcripts_search_vector", table_name="call_transcripts")
    op.execute("ALTER TABLE call_transcripts DROP COLUMN IF EXISTS search_vector")
    op.drop_index("uq_call_transcripts_tenant_provider_tx", table_name="call_transcripts")
    op.drop_index("uq_call_transcripts_tenant_recording", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_tenant_lifecycle", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_tenant_created", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_tenant_status", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_tenant_call", table_name="call_transcripts")
    op.drop_table("call_transcripts")

    op.drop_column("tenant_retention_settings", "analysis_retention_days")
    op.drop_column("tenant_retention_settings", "transcription_enabled")
    op.drop_column("tenant_retention_settings", "recording_enabled")

    op.drop_index(
        "ix_recording_objects_tenant_lifecycle", table_name="recording_objects"
    )
    op.drop_index("ix_recording_objects_tenant_call", table_name="recording_objects")
    op.drop_index(
        "uq_recording_objects_tenant_provider_rec", table_name="recording_objects"
    )
    op.drop_constraint(
        "ck_recording_objects_status", "recording_objects", type_="check"
    )
    op.drop_constraint(
        "ck_recording_objects_lifecycle", "recording_objects", type_="check"
    )
    op.drop_column("recording_objects", "lifecycle_status")
    op.drop_column("recording_objects", "recorded_at")
    op.drop_column("recording_objects", "checksum")
    op.drop_column("recording_objects", "duration_ms")
    op.drop_column("recording_objects", "provider_recording_id")
    op.drop_column("recording_objects", "provider")
