# Worker Operations

**Date:** 2026-10-06 (Phase 3)

## Processes

| Command | Role |
|---------|------|
| `python -m callbot_platform.workers.run_outbox` | SMS / webhook / email delivery |
| `python -m callbot_platform.workers.run_jobs` | Twilio / LiveKit / Stripe provisioning |

Run **multiple replicas** of each. Claim uses `FOR UPDATE SKIP LOCKED` (Postgres).

## Lifecycle

- SIGTERM / SIGINT → stop claiming new work
- Current item finishes when possible
- `JOB_SHUTDOWN_TIMEOUT_SECONDS` documents expected drain bound

## Leases

| Setting | Default |
|---------|---------|
| `OUTBOX_LEASE_SECONDS` | 120 |
| `JOB_LEASE_SECONDS` | 180 |

Crashed workers do not permanently own rows; expired leases return to `pending`.

## DLQ

Dead-letter jobs: `status=dead_letter`.

Ops (admin session):

- `GET /api/admin/jobs/dead-letter`
- `GET /api/admin/jobs/{id}`
- `POST /api/admin/jobs/{id}/retry`
- `POST /api/admin/jobs/retry-batch`
- `POST /api/admin/jobs/{id}/cancel`

Replay preserves idempotency keys; handlers must stay idempotent.

## Metrics (structured logs)

`jobs_processed_total`, `jobs_failed_total`, `jobs_retried_total`, `jobs_dead_lettered_total`, `jobs_lease_reclaimed_total`, latency observations.

## Tenant context

Workers set `TenantContext(source=JOB)` from the row’s `tenant_id` before handler execution.
