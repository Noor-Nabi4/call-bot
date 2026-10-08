"""Phase 25 Communication Templates: templates, versions, customer prefs, TECHNICIAN_ARRIVED."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0053_communication_templates"
down_revision = "0052_human_handoff"
branch_labels = None
depends_on = None

_EVENT_TYPES = (
    "CALL_COMPLETED",
    "CALL_TRANSCRIBED",
    "CALL_ANALYZED",
    "CALL_CLASSIFIED",
    "HANDOFF_CREATED",
    "HANDOFF_ASSIGNED",
    "HANDOFF_CONNECTED",
    "HANDOFF_COMPLETED",
    "LEAD_CREATED",
    "JOB_CREATED",
    "APPOINTMENT_CREATED",
    "APPOINTMENT_REMINDER",
    "TECHNICIAN_DISPATCHED",
    "TECHNICIAN_ARRIVED",
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
    "CALL_TRANSCRIBED",
    "CALL_ANALYZED",
    "CALL_CLASSIFIED",
    "HANDOFF_CREATED",
    "HANDOFF_ASSIGNED",
    "HANDOFF_CONNECTED",
    "HANDOFF_COMPLETED",
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

_SMS_KEYS = (
    "BOOKING_CONFIRMATION",
    "APPOINTMENT_REMINDER",
    "TECHNICIAN_EN_ROUTE",
    "TECHNICIAN_ARRIVED",
    "JOB_COMPLETED",
    "INVOICE",
    "PAYMENT",
    "REVIEW_REQUEST",
)
_EMAIL_KEYS = (
    "BOOKING",
    "ESTIMATE",
    "INVOICE",
    "RECEIPT",
    "REMINDER",
    "REVIEW",
)


def upgrade() -> None:
    op.create_table(
        "communication_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("template_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("active_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "channel",
            "template_key",
            name="uq_communication_templates_tenant_channel_key",
        ),
        sa.CheckConstraint(
            "channel IN ('SMS','EMAIL')",
            name="ck_communication_templates_channel",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE','ARCHIVED')",
            name="ck_communication_templates_status",
        ),
        sa.CheckConstraint(
            "template_key IN ("
            + ", ".join(f"'{k}'" for k in (*_SMS_KEYS, *_EMAIL_KEYS))
            + ")",
            name="ck_communication_templates_key",
        ),
    )
    op.create_index(
        "ix_communication_templates_tenant_status",
        "communication_templates",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_communication_templates_tenant_channel_key",
        "communication_templates",
        ["tenant_id", "channel", "template_key"],
    )

    op.create_table(
        "communication_template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("communication_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("subject_template", sa.Text(), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "template_id",
            "version",
            name="uq_communication_template_versions_template_version",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','SUPERSEDED')",
            name="ck_communication_template_versions_status",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_communication_template_versions_version",
        ),
    )
    op.create_index(
        "ix_comm_template_versions_tenant_template",
        "communication_template_versions",
        ["tenant_id", "template_id"],
    )
    op.create_index(
        "ix_comm_template_versions_template_status",
        "communication_template_versions",
        ["template_id", "status"],
    )

    op.add_column(
        "customers",
        sa.Column(
            "sms_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "email_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "marketing_sms_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "marketing_email_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

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
    prev = ", ".join(f"'{e}'" for e in _EVENT_TYPES_PREV)
    op.create_check_constraint(
        "ck_automation_events_type",
        "automation_events",
        f"event_type IN ({prev})",
    )

    op.drop_column("customers", "marketing_email_allowed")
    op.drop_column("customers", "marketing_sms_allowed")
    op.drop_column("customers", "email_allowed")
    op.drop_column("customers", "sms_allowed")

    op.drop_index(
        "ix_comm_template_versions_template_status",
        table_name="communication_template_versions",
    )
    op.drop_index(
        "ix_comm_template_versions_tenant_template",
        table_name="communication_template_versions",
    )
    op.drop_table("communication_template_versions")

    op.drop_index(
        "ix_communication_templates_tenant_channel_key",
        table_name="communication_templates",
    )
    op.drop_index(
        "ix_communication_templates_tenant_status",
        table_name="communication_templates",
    )
    op.drop_table("communication_templates")
