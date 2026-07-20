"""SQLAlchemy models package — re-exports for import compatibility."""

from __future__ import annotations

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid
from callbot_platform.db.models.billing import StripeWebhookEvent, TenantSubscription
from callbot_platform.db.models.crm import (
    Call,
    Customer,
    CustomerPhone,
    Lead,
    TenantAgentSettings,
)
from callbot_platform.db.models.handoff import (
    TenantHandoffSettings,
    TenantRetentionSettings,
)
from callbot_platform.db.models.jobs import Job, JobNote, Technician, TenantUser
from callbot_platform.db.models.knowledge import KnowledgeArticle
from callbot_platform.db.models.scheduling import (
    Appointment,
    NotificationOutbox,
    TenantScheduleSettings,
    default_weekly_hours,
)
from callbot_platform.db.models.tenant import (
    TelephonyAuditEvent,
    TelephonyIdempotencyKey,
    Tenant,
    TenantPhoneNumber,
    TenantTwilioSubaccount,
)

__all__ = [
    "Appointment",
    "Base",
    "Call",
    "Customer",
    "CustomerPhone",
    "Job",
    "JobNote",
    "JsonType",
    "KnowledgeArticle",
    "Lead",
    "NotificationOutbox",
    "StripeWebhookEvent",
    "Technician",
    "TelephonyAuditEvent",
    "TelephonyIdempotencyKey",
    "Tenant",
    "TenantAgentSettings",
    "TenantHandoffSettings",
    "TenantPhoneNumber",
    "TenantRetentionSettings",
    "TenantScheduleSettings",
    "TenantSubscription",
    "TenantTwilioSubaccount",
    "TenantUser",
    "_utcnow",
    "_uuid",
    "default_weekly_hours",
]
