"""Phase 25 communication template catalogs."""

from __future__ import annotations

from enum import StrEnum

MAX_BODY_TEMPLATE_LEN = 4000
MAX_SUBJECT_TEMPLATE_LEN = 200
MAX_RENDERED_SMS_LEN = 1600
MAX_RENDERED_EMAIL_LEN = 50_000
MAX_EXPANSION_DEPTH = 1  # no recursive template expansion


class CommChannel(StrEnum):
    SMS = "SMS"
    EMAIL = "EMAIL"


class TemplateStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class VersionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class SmsTemplateKey(StrEnum):
    BOOKING_CONFIRMATION = "BOOKING_CONFIRMATION"
    APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"
    TECHNICIAN_EN_ROUTE = "TECHNICIAN_EN_ROUTE"
    TECHNICIAN_ARRIVED = "TECHNICIAN_ARRIVED"
    JOB_COMPLETED = "JOB_COMPLETED"
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"
    REVIEW_REQUEST = "REVIEW_REQUEST"


class EmailTemplateKey(StrEnum):
    BOOKING = "BOOKING"
    ESTIMATE = "ESTIMATE"
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    REMINDER = "REMINDER"
    REVIEW = "REVIEW"


SMS_TEMPLATE_KEYS: frozenset[str] = frozenset(k.value for k in SmsTemplateKey)
EMAIL_TEMPLATE_KEYS: frozenset[str] = frozenset(k.value for k in EmailTemplateKey)
ALL_TEMPLATE_KEYS: frozenset[str] = SMS_TEMPLATE_KEYS | EMAIL_TEMPLATE_KEYS

# Marketing / review — require marketing_* preference flags.
MARKETING_TEMPLATE_KEYS: frozenset[str] = frozenset(
    {
        SmsTemplateKey.REVIEW_REQUEST.value,
        EmailTemplateKey.REVIEW.value,
    }
)

# Shared allow-list of all variable paths (fail closed on unknown).
ALL_VARIABLES: frozenset[str] = frozenset(
    {
        "customer.first_name",
        "customer.last_name",
        "customer.full_name",
        "customer.phone",
        "customer.email",
        "appointment.id",
        "appointment.date",
        "appointment.time",
        "appointment.service",
        "appointment.address",
        "appointment.confirmation_code",
        "job.id",
        "job.number",
        "job.status",
        "job.service",
        "technician.name",
        "technician.phone",
        "invoice.number",
        "invoice.total",
        "invoice.balance_due",
        "invoice.due_date",
        "invoice.payment_url",
        "estimate.number",
        "estimate.total",
        "estimate.status",
        "estimate.approval_url",
        "payment.amount",
        "payment.date",
        "payment.status",
        "payment.receipt_url",
        "business.name",
        "business.phone",
        "business.email",
        "business.website",
        "business.address",
        "review.url",
    }
)

# Variables allowed per template key (channel-agnostic key → subset).
TEMPLATE_VARIABLES: dict[str, frozenset[str]] = {
    SmsTemplateKey.BOOKING_CONFIRMATION.value: frozenset(
        {
            "customer.first_name",
            "customer.full_name",
            "appointment.service",
            "appointment.date",
            "appointment.time",
            "appointment.confirmation_code",
            "business.name",
            "business.phone",
        }
    ),
    SmsTemplateKey.APPOINTMENT_REMINDER.value: frozenset(
        {
            "customer.first_name",
            "appointment.service",
            "appointment.date",
            "appointment.time",
            "business.name",
            "business.phone",
        }
    ),
    SmsTemplateKey.TECHNICIAN_EN_ROUTE.value: frozenset(
        {
            "customer.first_name",
            "technician.name",
            "job.service",
            "business.name",
        }
    ),
    SmsTemplateKey.TECHNICIAN_ARRIVED.value: frozenset(
        {
            "customer.first_name",
            "technician.name",
            "business.name",
        }
    ),
    SmsTemplateKey.JOB_COMPLETED.value: frozenset(
        {
            "customer.first_name",
            "job.service",
            "job.number",
            "business.name",
        }
    ),
    SmsTemplateKey.INVOICE.value: frozenset(
        {
            "customer.first_name",
            "invoice.number",
            "invoice.balance_due",
            "invoice.payment_url",
            "business.name",
        }
    ),
    SmsTemplateKey.PAYMENT.value: frozenset(
        {
            "customer.first_name",
            "payment.amount",
            "business.name",
        }
    ),
    SmsTemplateKey.REVIEW_REQUEST.value: frozenset(
        {
            "customer.first_name",
            "business.name",
            "review.url",
        }
    ),
    EmailTemplateKey.BOOKING.value: frozenset(
        {
            "customer.first_name",
            "customer.full_name",
            "appointment.service",
            "appointment.date",
            "appointment.time",
            "appointment.address",
            "appointment.confirmation_code",
            "business.name",
            "business.phone",
            "business.email",
            "business.address",
        }
    ),
    EmailTemplateKey.ESTIMATE.value: frozenset(
        {
            "customer.first_name",
            "estimate.number",
            "estimate.total",
            "estimate.status",
            "estimate.approval_url",
            "business.name",
            "business.phone",
        }
    ),
    EmailTemplateKey.INVOICE.value: frozenset(
        {
            "customer.first_name",
            "invoice.number",
            "invoice.total",
            "invoice.balance_due",
            "invoice.due_date",
            "invoice.payment_url",
            "business.name",
            "business.phone",
        }
    ),
    EmailTemplateKey.RECEIPT.value: frozenset(
        {
            "customer.first_name",
            "payment.amount",
            "payment.date",
            "payment.status",
            "payment.receipt_url",
            "invoice.number",
            "business.name",
        }
    ),
    EmailTemplateKey.REMINDER.value: frozenset(
        {
            "customer.first_name",
            "appointment.service",
            "appointment.date",
            "appointment.time",
            "business.name",
            "business.phone",
        }
    ),
    EmailTemplateKey.REVIEW.value: frozenset(
        {
            "customer.first_name",
            "business.name",
            "review.url",
        }
    ),
}

# Default event → (channel, template_key) suggestions for docs / seeding helpers.
DEFAULT_EVENT_MAPPINGS: tuple[tuple[str, str, str], ...] = (
    ("APPOINTMENT_CREATED", "SMS", "BOOKING_CONFIRMATION"),
    ("APPOINTMENT_CREATED", "EMAIL", "BOOKING"),
    ("APPOINTMENT_REMINDER", "SMS", "APPOINTMENT_REMINDER"),
    ("APPOINTMENT_REMINDER", "EMAIL", "REMINDER"),
    ("TECHNICIAN_DISPATCHED", "SMS", "TECHNICIAN_EN_ROUTE"),
    ("TECHNICIAN_ARRIVED", "SMS", "TECHNICIAN_ARRIVED"),
    ("JOB_COMPLETED", "SMS", "JOB_COMPLETED"),
    ("JOB_COMPLETED", "SMS", "REVIEW_REQUEST"),
    ("INVOICE_CREATED", "SMS", "INVOICE"),
    ("INVOICE_CREATED", "EMAIL", "INVOICE"),
    ("PAYMENT_COMPLETED", "SMS", "PAYMENT"),
    ("PAYMENT_COMPLETED", "EMAIL", "RECEIPT"),
    ("ESTIMATE_SENT", "EMAIL", "ESTIMATE"),
)
