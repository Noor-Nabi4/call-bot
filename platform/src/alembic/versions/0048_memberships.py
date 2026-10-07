"""Phase 20 Memberships: plans, customer memberships, billing periods, entitlements."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0048_memberships"
down_revision = "0047_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "membership_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column(
            "monthly_price", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column(
            "annual_price", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "priority_scheduling",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("discount_type", sa.String(32), nullable=True),
        sa.Column("discount_value", sa.Numeric(19, 4), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_membership_plans_tenant_name"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','INACTIVE','ARCHIVED')",
            name="ck_membership_plans_status",
        ),
        sa.CheckConstraint(
            "monthly_price >= 0", name="ck_membership_plans_monthly_nonneg"
        ),
        sa.CheckConstraint(
            "annual_price >= 0", name="ck_membership_plans_annual_nonneg"
        ),
        sa.CheckConstraint(
            "(discount_type IS NULL AND discount_value IS NULL) OR "
            "(discount_type IN ('PERCENTAGE','FIXED_AMOUNT') AND discount_value IS NOT NULL)",
            name="ck_membership_plans_discount_shape",
        ),
        sa.CheckConstraint(
            "discount_value IS NULL OR discount_value >= 0",
            name="ck_membership_plans_discount_nonneg",
        ),
    )
    op.create_index(
        "ix_membership_plans_tenant_status",
        "membership_plans",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_membership_plans_tenant_created",
        "membership_plans",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "membership_plan_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("membership_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("included_quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "plan_id",
            "service_id",
            name="uq_membership_plan_services_plan_service",
        ),
        sa.CheckConstraint(
            "included_quantity > 0",
            name="ck_membership_plan_services_qty_positive",
        ),
    )
    op.create_index(
        "ix_membership_plan_services_tenant_plan",
        "membership_plan_services",
        ["tenant_id", "plan_id"],
    )

    op.create_table(
        "customer_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("membership_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("billing_interval", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "pending_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("membership_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("pending_billing_interval", sa.String(16), nullable=True),
        sa.Column(
            "last_invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("idempotency_request_hash", sa.String(64), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_customer_memberships_tenant_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'PENDING','ACTIVE','PAST_DUE','CANCELLED','EXPIRED','PAUSED'"
            ")",
            name="ck_customer_memberships_status",
        ),
        sa.CheckConstraint(
            "billing_interval IN ('MONTHLY','ANNUAL')",
            name="ck_customer_memberships_interval",
        ),
        sa.CheckConstraint(
            "pending_billing_interval IS NULL OR "
            "pending_billing_interval IN ('MONTHLY','ANNUAL')",
            name="ck_customer_memberships_pending_interval",
        ),
        sa.CheckConstraint(
            "current_period_end > current_period_start",
            name="ck_customer_memberships_period",
        ),
    )
    op.create_index(
        "ix_customer_memberships_tenant_status",
        "customer_memberships",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_customer_memberships_tenant_customer",
        "customer_memberships",
        ["tenant_id", "customer_id"],
    )
    op.create_index(
        "ix_customer_memberships_tenant_plan",
        "customer_memberships",
        ["tenant_id", "plan_id"],
    )
    op.create_index(
        "ix_customer_memberships_tenant_period_end",
        "customer_memberships",
        ["tenant_id", "current_period_end"],
    )
    op.create_index(
        "ix_customer_memberships_tenant_created",
        "customer_memberships",
        ["tenant_id", "created_at"],
    )
    # One non-terminal membership per customer (DB-enforced).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_customer_memberships_one_open
        ON customer_memberships (tenant_id, customer_id)
        WHERE status IN ('PENDING', 'ACTIVE', 'PAST_DUE', 'PAUSED')
        """
    )

    op.create_table(
        "membership_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "from_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("membership_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "to_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("membership_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False, server_default="user"),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_membership_history_tenant_membership",
        "membership_history",
        ["tenant_id", "membership_id", "created_at"],
    )

    op.create_table(
        "membership_billing_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "membership_id",
            "period_start",
            name="uq_membership_billing_period_start",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_membership_billing_periods_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','PAID','VOID','FAILED')",
            name="ck_membership_billing_periods_status",
        ),
        sa.CheckConstraint(
            "amount >= 0", name="ck_membership_billing_periods_amount_nonneg"
        ),
        sa.CheckConstraint(
            "period_end > period_start",
            name="ck_membership_billing_periods_window",
        ),
    )
    op.create_index(
        "ix_membership_billing_periods_tenant_invoice",
        "membership_billing_periods",
        ["tenant_id", "invoice_id"],
    )
    op.create_index(
        "ix_membership_billing_periods_tenant_membership",
        "membership_billing_periods",
        ["tenant_id", "membership_id"],
    )

    op.create_table(
        "membership_entitlement_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "membership_id",
            "appointment_id",
            "service_id",
            name="uq_membership_entitlement_usage_appt",
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_membership_entitlement_usage_qty"
        ),
    )
    op.create_index(
        "ix_membership_entitlement_usage_tenant_membership",
        "membership_entitlement_usage",
        ["tenant_id", "membership_id"],
    )
    op.create_index(
        "ix_membership_entitlement_usage_tenant_appointment",
        "membership_entitlement_usage",
        ["tenant_id", "appointment_id"],
    )


def downgrade() -> None:
    op.drop_table("membership_entitlement_usage")
    op.drop_table("membership_billing_periods")
    op.drop_table("membership_history")
    op.execute("DROP INDEX IF EXISTS uq_customer_memberships_one_open")
    op.drop_table("customer_memberships")
    op.drop_table("membership_plan_services")
    op.drop_table("membership_plans")
