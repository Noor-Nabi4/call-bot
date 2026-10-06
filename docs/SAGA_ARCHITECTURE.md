# Saga / Async Job Architecture

**Date:** 2026-10-06 (Phase 3)  
**Table:** `async_jobs`  
**Worker:** `python -m callbot_platform.workers.run_jobs`

## Pattern

```text
API validates
  → DB TX: business intent + async_jobs row (pending)
  → COMMIT
  → worker claims (FOR UPDATE SKIP LOCKED) + lease
  → COMMIT claim
  → provider HTTP (Twilio / LiveKit / Stripe)
  → persist provider IDs / status
  → SUCCEEDED | RETRY_WAIT | DEAD_LETTER
```

External I/O never runs while holding an open request transaction.

## Job types

| Type | Purpose |
|------|---------|
| `telephony.provision_purchase` | Path B Twilio purchase + LiveKit |
| `telephony.release` | Path B Twilio + LiveKit release |
| `telephony.refresh_dispatch` | LiveKit dispatch metadata after profile assign |
| `stripe.signup_provision` | Stripe customer + Checkout URL |
| `stripe.checkout_provision` | Resume Checkout |

## Idempotency

Deterministic keys, e.g.:

- `tenant:{tenant_id}:phone:{phone_id}:provision`
- `tenant:{tenant_id}:billing:signup`
- Stripe Customer: `tenant:{tenant_id}:stripe:customer`

Handlers record `steps_completed` on phone `provisioning_details` so retries skip finished steps.

## Leases

`lease_expires_at` + `claimed_by`. Expired `running` rows are reclaimed to `pending`.

## Relationship to notification_outbox

`notification_outbox` remains SMS/email/webhook shaped. Provisioning uses `async_jobs`.

## Inline post-commit

HTTP purchase/connect/signup routes commit, then run the job once in-process for UX, while the same worker code path handles retries/replicas.
