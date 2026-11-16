"""Default template copy for tenant seeding."""

from __future__ import annotations

from callbot_platform.communication_templates.constants import (
    EmailTemplateKey,
    SmsTemplateKey,
)

# (channel, template_key, name, description, subject, body)
DEFAULT_TEMPLATES: tuple[tuple[str, str, str, str, str | None, str], ...] = (
    (
        "SMS",
        SmsTemplateKey.BOOKING_CONFIRMATION.value,
        "Booking confirmation",
        "Sent when an appointment is created",
        None,
        "Hi {{customer.first_name}}, your {{appointment.service}} appointment with "
        "{{business.name}} is confirmed for {{appointment.date}} at "
        "{{appointment.time}}. Reply if you need help.",
    ),
    (
        "SMS",
        SmsTemplateKey.APPOINTMENT_REMINDER.value,
        "Appointment reminder",
        "Reminder before the appointment",
        None,
        "Reminder: your {{appointment.service}} appointment with {{business.name}} "
        "is scheduled for {{appointment.date}} at {{appointment.time}}.",
    ),
    (
        "SMS",
        SmsTemplateKey.TECHNICIAN_EN_ROUTE.value,
        "Technician en route",
        "Sent when a technician is dispatched",
        None,
        "Hi {{customer.first_name}}, your technician {{technician.name}} is on the "
        "way for your {{job.service}} service. — {{business.name}}",
    ),
    (
        "SMS",
        SmsTemplateKey.TECHNICIAN_ARRIVED.value,
        "Technician arrived",
        "Sent when the technician arrives",
        None,
        "Hi {{customer.first_name}}, {{technician.name}} has arrived for your "
        "scheduled service. — {{business.name}}",
    ),
    (
        "SMS",
        SmsTemplateKey.JOB_COMPLETED.value,
        "Job completed",
        "Sent when a job is completed",
        None,
        "Hi {{customer.first_name}}, your {{job.service}} job has been completed. "
        "Thank you for choosing {{business.name}}.",
    ),
    (
        "SMS",
        SmsTemplateKey.INVOICE.value,
        "Invoice",
        "Invoice balance notice",
        None,
        "Hi {{customer.first_name}}, invoice {{invoice.number}} from "
        "{{business.name}} is {{invoice.balance_due}} due. Pay securely: "
        "{{invoice.payment_url}}",
    ),
    (
        "SMS",
        SmsTemplateKey.PAYMENT.value,
        "Payment received",
        "Payment confirmation",
        None,
        "Hi {{customer.first_name}}, we received your payment of {{payment.amount}} "
        "for {{business.name}}. Thank you.",
    ),
    (
        "SMS",
        SmsTemplateKey.REVIEW_REQUEST.value,
        "Review request",
        "Ask for customer feedback (marketing)",
        None,
        "Hi {{customer.first_name}}, thanks for choosing {{business.name}}. "
        "We'd appreciate your feedback: {{review.url}}",
    ),
    (
        "EMAIL",
        EmailTemplateKey.BOOKING.value,
        "Booking confirmation",
        "Email when an appointment is booked",
        "Your appointment with {{business.name}} is confirmed",
        "Hi {{customer.first_name}},\n\n"
        "Your {{appointment.service}} appointment with {{business.name}} is "
        "confirmed for {{appointment.date}} at {{appointment.time}}.\n"
        "Confirmation: {{appointment.confirmation_code}}\n\n"
        "{{business.name}}\n{{business.phone}}\n{{business.email}}",
    ),
    (
        "EMAIL",
        EmailTemplateKey.ESTIMATE.value,
        "Estimate",
        "Email when an estimate is sent",
        "Estimate {{estimate.number}} from {{business.name}}",
        "Hi {{customer.first_name}},\n\n"
        "Estimate {{estimate.number}} for {{estimate.total}} "
        "(status: {{estimate.status}}).\n"
        "Review and approve: {{estimate.approval_url}}\n\n"
        "{{business.name}}\n{{business.phone}}",
    ),
    (
        "EMAIL",
        EmailTemplateKey.INVOICE.value,
        "Invoice",
        "Invoice email",
        "Invoice {{invoice.number}} from {{business.name}}",
        "Hi {{customer.first_name}},\n\n"
        "Invoice {{invoice.number}} — total {{invoice.total}}, "
        "balance due {{invoice.balance_due}} (due {{invoice.due_date}}).\n"
        "Pay securely: {{invoice.payment_url}}\n\n"
        "{{business.name}}\n{{business.phone}}",
    ),
    (
        "EMAIL",
        EmailTemplateKey.RECEIPT.value,
        "Payment receipt",
        "Receipt after payment",
        "Payment receipt from {{business.name}}",
        "Hi {{customer.first_name}},\n\n"
        "We received {{payment.amount}} on {{payment.date}} "
        "(status: {{payment.status}}) for invoice {{invoice.number}}.\n"
        "Receipt: {{payment.receipt_url}}\n\n"
        "{{business.name}}",
    ),
    (
        "EMAIL",
        EmailTemplateKey.REMINDER.value,
        "Appointment reminder",
        "Email reminder before appointment",
        "Reminder: your appointment with {{business.name}}",
        "Hi {{customer.first_name}},\n\n"
        "Reminder: your {{appointment.service}} appointment is "
        "{{appointment.date}} at {{appointment.time}}.\n\n"
        "{{business.name}}\n{{business.phone}}",
    ),
    (
        "EMAIL",
        EmailTemplateKey.REVIEW.value,
        "Review request",
        "Ask for feedback (marketing)",
        "How was your experience with {{business.name}}?",
        "Hi {{customer.first_name}},\n\n"
        "Thanks for choosing {{business.name}}. "
        "We'd love your feedback: {{review.url}}\n\n"
        "{{business.name}}",
    ),
)
