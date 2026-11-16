# Communication Templates (Phase 25)

Tenant-scoped SMS/Email templates for Phase 22 automations. Rendering is server-side and fail-closed; delivery uses the existing NotificationService → NotificationOutbox → provider path.

## Architecture

```text
Business Event
  → Phase 22 Automation Engine (SEND_SMS / SEND_EMAIL + template_key)
  → CommunicationTemplateService (load active version + render)
  → NotificationService.enqueue_*
  → NotificationOutbox
  → SMS (Twilio) / Email (provider TBD)
```

Phase 25 owns templates, versions, validation, variable registry, and admin UI.  
It does **not** own delivery, retries, or a second notification pipeline.

## Migration

`0053_communication_templates` (head after Phase 24).

Tables: `communication_templates`, `communication_template_versions`  
Customer prefs: `sms_allowed`, `email_allowed`, `marketing_sms_allowed`, `marketing_email_allowed`  
Event: `TECHNICIAN_ARRIVED`

## Template keys

### SMS

`BOOKING_CONFIRMATION`, `APPOINTMENT_REMINDER`, `TECHNICIAN_EN_ROUTE`, `TECHNICIAN_ARRIVED`, `JOB_COMPLETED`, `INVOICE`, `PAYMENT`, `REVIEW_REQUEST`

### Email

`BOOKING`, `ESTIMATE`, `INVOICE`, `RECEIPT`, `REMINDER`, `REVIEW`

## Versioning

Edits create DRAFT versions (or immediate publish). Historical outbox rows store rendered body plus `payload.template_key` / `template_version`.

## Automation config

```json
{ "type": "SEND_SMS", "config": { "template_key": "APPOINTMENT_REMINDER" } }
```

Inline `body` still works for backward compatibility.

## Preferences

- Transactional: require `sms_allowed` / `email_allowed`
- Marketing (`REVIEW_REQUEST` / `REVIEW`): also require `marketing_*_allowed`

## Status

```text
APPLICATION COMPLETE / FROZEN
PRODUCTION BLOCKED
```

Verification (local disposable PG `call_bot_comm_verify`): migration
upgrade/downgrade/re-upgrade from stamped `0052` **PASS**; constraint +
EXPLAIN index scans **PASS**.

Primary blockers: live Twilio delivery, email SMTP/SES provider (outbox still
skips), staging.

## Out of scope

New notification engine, visual campaign builder, contact-center presence.
