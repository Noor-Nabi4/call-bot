"""Phase 22 Automation Engine catalogs."""

from __future__ import annotations

from enum import StrEnum

# Hard maximum automation recursion depth (event chain).
MAX_AUTOMATION_DEPTH = 3
MAX_ACTION_ATTEMPTS = 5
DEFAULT_APPOINTMENT_REMINDER_HOURS = 24


class AutomationEventType(StrEnum):
    CALL_COMPLETED = "CALL_COMPLETED"
    CALL_TRANSCRIBED = "CALL_TRANSCRIBED"
    CALL_ANALYZED = "CALL_ANALYZED"
    CALL_CLASSIFIED = "CALL_CLASSIFIED"
    LEAD_CREATED = "LEAD_CREATED"
    JOB_CREATED = "JOB_CREATED"
    APPOINTMENT_CREATED = "APPOINTMENT_CREATED"
    APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"
    TECHNICIAN_DISPATCHED = "TECHNICIAN_DISPATCHED"
    JOB_COMPLETED = "JOB_COMPLETED"
    ESTIMATE_SENT = "ESTIMATE_SENT"
    ESTIMATE_APPROVED = "ESTIMATE_APPROVED"
    INVOICE_CREATED = "INVOICE_CREATED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_SHIPPED = "ORDER_SHIPPED"


class WorkflowStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


class VersionStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SUPPRESSED = "SUPPRESSED"


class ActionExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRYING = "RETRYING"


class ActionType(StrEnum):
    SEND_SMS = "SEND_SMS"
    SEND_EMAIL = "SEND_EMAIL"
    CREATE_TASK = "CREATE_TASK"
    CREATE_JOB = "CREATE_JOB"
    CREATE_APPOINTMENT = "CREATE_APPOINTMENT"
    SEND_PAYMENT_LINK = "SEND_PAYMENT_LINK"
    REQUEST_REVIEW = "REQUEST_REVIEW"
    WEBHOOK = "WEBHOOK"


class ConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


# Allow-listed condition field paths (server resolves against DB/payload).
CONDITION_FIELDS: frozenset[str] = frozenset(
    {
        "job.status",
        "job.priority",
        "job.service_type",
        "job.customer_id",
        "customer.status",
        "customer.name",
        "customer.email",
        "customer.phone",
        "invoice.total",
        "invoice.balance_due",
        "invoice.status",
        "payment.amount",
        "payment.status",
        "order.status",
        "estimate.status",
        "appointment.status",
        "call.classification",
        "call.sentiment",
        "call.intent",
        "event.type",
        "event.entity_type",
    }
)

SAFE_TEMPLATE_KEYS: frozenset[str] = frozenset(
    {
        "customer.first_name",
        "customer.name",
        "customer.email",
        "customer.phone",
        "job.number",
        "job.status",
        "invoice.number",
        "invoice.balance_due",
        "appointment.confirmation_code",
        "business.name",
        "review.url",
    }
)

EVENT_TYPES = frozenset(e.value for e in AutomationEventType)
ACTION_TYPES = frozenset(a.value for a in ActionType)
