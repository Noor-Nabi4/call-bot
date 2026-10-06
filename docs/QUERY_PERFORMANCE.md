# Query Performance

**Date:** 2026-10-06 (final production readiness verification)

```text
STAGING EXPLAIN ANALYZE = NOT EXECUTED
REASON = no staging database with representative data available
LOCAL EXPLAIN ANALYZE = VERIFIED (empty restored DB upgraded to 0022_phase3_async_jobs)
```

Local DB: `call_bot_dr_20261006113707` (all measured tables had **0 rows**). Empty-table Seq Scans are expected and are **not** evidence for or against production index quality.

## Hot paths reviewed

| Table | Access pattern | Existing support | Local plan (0 rows) | Execution time |
|-------|----------------|------------------|---------------------|----------------|
| `async_jobs` | dequeue by status + next_attempt | `ix_async_jobs_dequeue` | Bitmap Index Scan on dequeue index → Sort → Limit | 0.082 ms |
| `notification_outbox` | dequeue by status + next_attempt | `ix_notification_outbox_dequeue` | Seq Scan (empty) → Sort → Limit | 0.025 ms |
| `calls` | tenant + time / cursor list | `ix_calls_tenant_*` | Seq Scan (empty) → Sort → Limit | 0.017 ms |
| `leads` | tenant list | existing tenant indexes | Seq Scan (empty) → Sort → Limit | 0.014 ms |
| `appointments` | tenant + starts_at | existing indexes | Seq Scan (empty) → Sort → Limit | 0.015 ms |
| `jobs` | tenant list | existing indexes | Seq Scan (empty) → Sort → Limit | 0.014 ms |
| `agent_profiles` | tenant scoped | agent profile indexes | Seq Scan (empty) | 0.011 ms |
| `tenant_phone_numbers` | tenant list | `ix_tenant_phone_numbers_tenant_id` | Index Scan on tenant_id | 0.011 ms |
| `recording_objects` | retention cleanup | `ix_recording_objects_tenant_retention` | Seq Scan (empty; filter deleted_at + retention_until) | 0.056 ms |

## Plan issues / recommendations

| Query | Plan issue | Existing index | Recommended change |
|-------|------------|----------------|--------------------|
| async_jobs dequeue | None observed on empty set; uses dequeue index | `ix_async_jobs_dequeue` | None — re-check on staging volume |
| outbox / calls / leads / appointments / jobs | Seq Scan only because relation is empty; planner prefers seq over index at ~0 rows | dequeue / tenant indexes present | **Do not add indexes** until staging EXPLAIN shows sequential scans under load |
| recording retention without tenant predicate | Seq Scan on empty table; production retention should prefer tenant-scoped or partial index usage under volume | `ix_recording_objects_tenant_retention` (tenant_id, retention_until) | Re-run with tenant filter + real volume before changing indexes |

## Index policy

No new indexes added during this verification. Add indexes only after measured sequential scans on **staging with representative data**.

## Staging command (when available)

```bash
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, tenant_id FROM async_jobs
WHERE status IN ('pending', 'retry_wait')
  AND (next_attempt_at IS NULL OR next_attempt_at <= now())
ORDER BY created_at ASC
LIMIT 10;
```

Repeat for outbox dequeue, call list cursor queries, and retention cleanup.
