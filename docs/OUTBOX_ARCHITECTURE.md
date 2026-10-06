# Outbox Architecture

**Date:** 2026-10-06 (Phase 2)  
**Table:** `notification_outbox`  
**Worker:** `python -m callbot_platform.workers.run_outbox`

## Flow

```text
Business operation (appointment book / automation webhook)
       ↓
DB transaction: business row + outbox row (status=pending)
       ↓
COMMIT
       ↓
Outbox worker (claim FOR UPDATE SKIP LOCKED)
       ↓
COMMIT claim (status=processing)
       ↓
External provider (Twilio SMS / webhook HTTP / email)
       ↓
UPDATE sent | pending+backoff | dead_letter | skipped
```

## Channels

| Channel | Enqueued by | Delivered by |
|---------|-------------|--------------|
| `sms` | `NotificationService.enqueue_sms` | Twilio (`send_sms_now`) |
| `email` | `NotificationService.enqueue_email` | Skipped until SMTP configured |
| `webhook` | `AutomationService` `post_webhook` | `deliver_webhook` (httpx) |

## Worker settings

```text
OUTBOX_BATCH_SIZE
OUTBOX_MAX_RETRIES
OUTBOX_BASE_BACKOFF_SECONDS
OUTBOX_MAX_BACKOFF_SECONDS
OUTBOX_POLL_INTERVAL_SECONDS
```

## Idempotency

- Stable `idempotency_key` per tenant (unique)
- Twilio attempts `idempotency_key` on message create when supported
- Claim → commit before I/O so crashes do not leave forever-locked rows without retry path
- Retries use exponential backoff; after `OUTBOX_MAX_RETRIES` → `dead_letter`

## Multi-replica

Postgres: `FOR UPDATE SKIP LOCKED`. SQLite tests use `FOR UPDATE` without skip.

## Tenant context

Worker sets `TenantContext(source=JOB)` from the outbox row’s `tenant_id` before delivery.
