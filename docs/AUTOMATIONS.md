# Automation Engine (Phase 22)

Deterministic, durable, tenant-scoped workflows:

```text
WHEN event → IF conditions → THEN actions
```

Legacy single-action `automation_rules` (`/api/admin/automations`) remain for voice-era triggers. Phase 22 workflows live under `/api/admin/crm/automations`.

## Architecture

```text
Domain mutation (same TX)
  → automation_events (outbox)
  → AutomationEventWorker (combined outbox worker)
  → match ACTIVE workflows by trigger_event
  → evaluate allow-listed conditions (server DB lookups for financial fields)
  → automation_executions + automation_action_executions
  → actions via existing services / notification_outbox
```

Loop protection:

- `MAX_AUTOMATION_DEPTH = 3`
- `CREATE_JOB` forbidden on `JOB_CREATED`
- `CREATE_APPOINTMENT` forbidden on `APPOINTMENT_CREATED`

Idempotency: `UNIQUE(tenant_id, event_id, workflow_id)` and per-action idempotency keys.

## Events

`CALL_COMPLETED`, `LEAD_CREATED`, `JOB_CREATED`, `APPOINTMENT_CREATED`, `APPOINTMENT_REMINDER`, `TECHNICIAN_DISPATCHED`, `JOB_COMPLETED`, `ESTIMATE_SENT`, `ESTIMATE_APPROVED`, `INVOICE_CREATED`, `PAYMENT_COMPLETED`, `ORDER_CREATED`, `ORDER_SHIPPED`

Reminders: durable `automation_scheduled_events` (default 24h before appointment).

## Actions

`SEND_SMS`, `SEND_EMAIL`, `CREATE_TASK`, `CREATE_JOB`, `CREATE_APPOINTMENT`, `SEND_PAYMENT_LINK`, `REQUEST_REVIEW`, `WEBHOOK`

SMS/email/webhook enqueue `notification_outbox`. Jobs/appointments/payments call existing CRM services. Tasks use `automation_tasks`.

## Migration

`0050_automations`

## Worker

`python -m callbot_platform.workers.run_outbox` drains inventory + **automation_events** + notification outbox.

## RBAC

`automations.read|create|update|activate|delete|history` (+ legacy `automations.manage`)

## Known limitations

- Performance / EXPLAIN: NOT EXECUTED
- Staging/production: NOT EXECUTED
- Stripe/SMS/email live provider verification: NOT EXECUTED
- Workflow builder is structured (not a canvas); AI workflow generation not included
