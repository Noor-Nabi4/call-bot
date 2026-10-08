"""Phase 24 Human Handoff: departments, requests, assignments, history."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0052_human_handoff"
down_revision = "0051_call_intelligence"
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
    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("phone_e164", sa.String(32), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_departments_tenant_slug"),
        sa.CheckConstraint(
            "slug IN ('sales','support','dispatch','billing','emergency','other')",
            name="ck_departments_slug",
        ),
    )
    op.create_index(
        "ix_departments_tenant_active", "departments", ["tenant_id", "active"]
    )

    op.create_table(
        "handoff_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False, server_default="NORMAL"),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sms_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("department", sa.String(64), nullable=True),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "target_technician_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technicians.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "context_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.String(191), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "channel IN ('VOICE','SMS','CHAT')",
            name="ck_handoff_requests_channel",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','ROUTING','ASSIGNED','CONNECTED',"
            "'COMPLETED','FAILED','CANCELLED')",
            name="ck_handoff_requests_status",
        ),
        sa.CheckConstraint(
            "reason IN ('AI_REQUEST','CUSTOMER_REQUEST','EMERGENCY',"
            "'AFTER_HOURS','BUSINESS_RULE','MANUAL')",
            name="ck_handoff_requests_reason",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW','NORMAL','HIGH','URGENT','EMERGENCY')",
            name="ck_handoff_requests_priority",
        ),
    )
    op.create_index(
        "ix_handoff_requests_tenant_status",
        "handoff_requests",
        ["tenant_id", "status", "requested_at"],
    )
    op.create_index(
        "ix_handoff_requests_tenant_priority",
        "handoff_requests",
        ["tenant_id", "priority", "requested_at"],
    )
    op.create_index(
        "ix_handoff_requests_tenant_channel",
        "handoff_requests",
        ["tenant_id", "channel"],
    )
    op.create_index(
        "ix_handoff_requests_tenant_call",
        "handoff_requests",
        ["tenant_id", "call_id"],
    )
    op.create_index(
        "ix_handoff_requests_tenant_customer",
        "handoff_requests",
        ["tenant_id", "customer_id"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_handoff_requests_tenant_idem
        ON handoff_requests (tenant_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )

    op.create_table(
        "handoff_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "handoff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("handoff_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "assigned_technician_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technicians.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assignment_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timeout_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "assignment_type IN ('USER','DEPARTMENT','TECHNICIAN','QUEUE')",
            name="ck_handoff_assignments_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','ACCEPTED','REJECTED','TIMEOUT')",
            name="ck_handoff_assignments_status",
        ),
    )
    op.create_index(
        "ix_handoff_assignments_tenant_handoff",
        "handoff_assignments",
        ["tenant_id", "handoff_id"],
    )
    op.create_index(
        "ix_handoff_assignments_tenant_status",
        "handoff_assignments",
        ["tenant_id", "status", "assigned_at"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_handoff_assignments_active
        ON handoff_assignments (tenant_id, handoff_id)
        WHERE status IN ('PENDING','ACCEPTED')
        """
    )

    op.create_table(
        "handoff_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "handoff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("handoff_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('CREATED','ROUTED','ASSIGNED','CONNECTED',"
            "'COMPLETED','FAILED','CANCELLED','REJECTED')",
            name="ck_handoff_history_event",
        ),
    )
    op.create_index(
        "ix_handoff_history_handoff_created",
        "handoff_history",
        ["handoff_id", "created_at"],
    )
    op.create_index(
        "ix_handoff_history_tenant_created",
        "handoff_history",
        ["tenant_id", "created_at"],
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

    op.drop_index("ix_handoff_history_tenant_created", table_name="handoff_history")
    op.drop_index("ix_handoff_history_handoff_created", table_name="handoff_history")
    op.drop_table("handoff_history")

    op.drop_index("uq_handoff_assignments_active", table_name="handoff_assignments")
    op.drop_index(
        "ix_handoff_assignments_tenant_status", table_name="handoff_assignments"
    )
    op.drop_index(
        "ix_handoff_assignments_tenant_handoff", table_name="handoff_assignments"
    )
    op.drop_table("handoff_assignments")

    op.drop_index("uq_handoff_requests_tenant_idem", table_name="handoff_requests")
    op.drop_index("ix_handoff_requests_tenant_customer", table_name="handoff_requests")
    op.drop_index("ix_handoff_requests_tenant_call", table_name="handoff_requests")
    op.drop_index("ix_handoff_requests_tenant_channel", table_name="handoff_requests")
    op.drop_index("ix_handoff_requests_tenant_priority", table_name="handoff_requests")
    op.drop_index("ix_handoff_requests_tenant_status", table_name="handoff_requests")
    op.drop_table("handoff_requests")

    op.drop_index("ix_departments_tenant_active", table_name="departments")
    op.drop_table("departments")
