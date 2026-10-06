"""Initial telephony schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_telephony"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "tenant_phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("e164", sa.String(32), nullable=False),
        sa.Column("twilio_account_sid", sa.String(64), nullable=True),
        sa.Column("twilio_trunk_sid", sa.String(64), nullable=True),
        sa.Column("livekit_inbound_trunk_id", sa.String(128), nullable=True),
        sa.Column("livekit_dispatch_rule_id", sa.String(128), nullable=True),
        sa.Column("connection_status", sa.String(32), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("onboarding_path", sa.String(32), nullable=False),
        sa.Column("auth_method", sa.String(32), nullable=False),
        sa.Column("oauth_connection_id", sa.String(128), nullable=True),
        sa.Column("verification_token", sa.String(128), nullable=True),
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provisioning_state", sa.String(32), nullable=False),
        sa.Column("provisioning_details", sa.JSON(), nullable=False),
        sa.Column("last_purchase_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("e164", name="uq_tenant_phone_numbers_e164"),
    )
    op.create_index(
        "ix_tenant_phone_numbers_tenant_id", "tenant_phone_numbers", ["tenant_id"]
    )
    op.create_index(
        "ix_tenant_phone_numbers_livekit_trunk",
        "tenant_phone_numbers",
        ["livekit_inbound_trunk_id"],
    )
    op.create_table(
        "tenant_twilio_subaccounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("twilio_subaccount_sid", sa.String(64), nullable=False),
        sa.Column("encrypted_auth_token", sa.Text(), nullable=False),
        sa.Column("friendly_name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_twilio_subaccounts_tenant"),
        sa.UniqueConstraint(
            "twilio_subaccount_sid", name="uq_tenant_twilio_subaccounts_sid"
        ),
    )
    op.create_table(
        "telephony_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_ids", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("payload_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_telephony_audit_tenant_id", "telephony_audit_events", ["tenant_id"]
    )
    op.create_table(
        "telephony_idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "operation", "key", name="uq_telephony_idempotency"
        ),
    )


def downgrade() -> None:
    op.drop_table("telephony_idempotency_keys")
    op.drop_table("telephony_audit_events")
    op.drop_table("tenant_twilio_subaccounts")
    op.drop_table("tenant_phone_numbers")
    op.drop_table("tenants")
