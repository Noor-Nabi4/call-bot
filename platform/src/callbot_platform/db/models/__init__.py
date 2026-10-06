"""SQLAlchemy models package — re-exports for import compatibility."""

from __future__ import annotations

from callbot_platform.db.models.agent_profile import (
    AgentProfile,
    default_business_hours,
    default_enabled_tools,
)
from callbot_platform.db.models.api_keys import TenantApiKey
from callbot_platform.db.models.async_job import AsyncJob
from callbot_platform.db.models.automation import AutomationRule
from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid
from callbot_platform.db.models.billing import StripeWebhookEvent, TenantSubscription
from callbot_platform.db.models.branding import TenantBranding
from callbot_platform.db.models.cogs import CallCogs
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
from callbot_platform.db.models.queue import CallQueueItem
from callbot_platform.db.models.recordings import RecordingObject
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
    "AgentProfile",
    "Appointment",
    "AsyncJob",
    "AutomationRule",
    "Base",
    "Call",
    "CallCogs",
    "CallQueueItem",
    "Customer",
    "CustomerPhone",
    "Job",
    "JobNote",
    "JsonType",
    "KnowledgeArticle",
    "Lead",
    "NotificationOutbox",
    "RecordingObject",
    "StripeWebhookEvent",
    "Technician",
    "TelephonyAuditEvent",
    "TelephonyIdempotencyKey",
    "Tenant",
    "TenantAgentSettings",
    "TenantApiKey",
    "TenantBranding",
    "TenantHandoffSettings",
    "TenantPhoneNumber",
    "TenantRetentionSettings",
    "TenantScheduleSettings",
    "TenantSubscription",
    "TenantTwilioSubaccount",
    "TenantUser",
    "_utcnow",
    "_uuid",
    "default_business_hours",
    "default_enabled_tools",
    "default_weekly_hours",
]
