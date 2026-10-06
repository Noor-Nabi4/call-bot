# Query Performance

**Date:** 2026-10-06 (Phase 3.1)  
**Status:** `EXPLAIN ANALYZE` against production: **NOT EXECUTED** (no production/staging dataset access in this environment).

## Hot paths reviewed (code + existing indexes)

| Table | Access pattern | Existing support |
|-------|----------------|------------------|
| `calls` | tenant + time / cursor list | Phase 1/2 indexes |
| `notification_outbox` | dequeue by status + next_attempt | `ix_notification_outbox_dequeue` |
| `async_jobs` | dequeue by status + next_attempt | `ix_async_jobs_dequeue` |
| `tenant_phone_numbers` | e164 unique / tenant list | telephony indexes |
| `recording_objects` | tenant + retention | `ix_recording_objects_tenant_retention` |
| `agent_profiles` | tenant scoped | agent profile indexes |

## Local verification

SQLite test DB does not provide meaningful Postgres plans. When a staging Postgres is available:

```bash
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, tenant_id FROM async_jobs
WHERE status IN ('pending', 'retry_wait')
  AND (next_attempt_at IS NULL OR next_attempt_at <= now())
ORDER BY created_at ASC
LIMIT 10;
```

Repeat for outbox dequeue and call list cursor queries.

## Index policy

No new indexes added in Phase 3.1 — existing Phase 2/3 indexes cover dequeue and retention. Add indexes only after measured sequential scans on staging.
