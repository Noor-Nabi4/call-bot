# Disaster Recovery

**Date:** 2026-10-06 (final production readiness verification)  
**Status:** Local non-production restore drill **VERIFIED**. Managed/staging/production backup pipelines **NOT VERIFIED**.

## Latest drill (local Homebrew Postgres — non-production)

```text
STATUS = VERIFIED (local scratch only)
ENVIRONMENT = localhost PostgreSQL 17.9 (Homebrew)
SOURCE_DB = call_bot (alembic 0017_tenant_branding at backup)
RESTORE_DB = call_bot_dr_20261006113707
backup_timestamp = 2026-10-06T11:37:06Z
restore_start = 2026-10-06T11:37:07Z
restore_completion = 2026-10-06T11:37:09Z
RTO (this drill) = 2 seconds (dump restore only; excludes provisioning new host)
RPO (this drill) = ~1 second (age of dump at restore start)
POST_RESTORE = alembic upgrade head → 0022_phase3_async_jobs (no-op remaining)
APP = uvicorn against restore DB
  GET /liveness → {"status":"alive"} HTTP 200
  GET /readiness → {"status":"ready","checks":{"postgres":"ok","object_storage":"filesystem"}} HTTP 200
  SIGTERM → clean process exit
PRODUCTION / SUPABASE = NOT TOUCHED
MANAGED BACKUP PIPELINE = NOT EXECUTED (no cloud backup credentials / runbook execution)
```

## Goals

| Metric | Target (configure per env) |
|--------|----------------------------|
| RPO | ≤ 24h (adjust with continuous WAL archiving) |
| RTO | ≤ 4h for shared-DB fleet restore |

Do **not** claim production backups exist until the checklist below is executed against the real backup system.

## Database

### Required configuration

- Automated Postgres backups (managed provider snapshots **or** `pg_basebackup` / WAL-G / Barman)
- Retention: ≥ 7 daily + ≥ 4 weekly
- Point-in-time recovery (PITR) enabled where available
- Dedicated-tenant DBs: same backup policy as shared (or documented exception)

### Fleet connection math (document per deploy)

```text
total_connections ≈
  API_replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
+ job_worker_replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
+ outbox_worker_replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
+ admin/migration sessions
```

Default settings observed in code: `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10` → 15 connections per process.
Keep total under Postgres `max_connections` with headroom.

### Restore verification procedure

1. Provision a scratch Postgres instance.
2. Restore latest backup (and WAL to a known timestamp if using PITR).
3. Set `DATABASE_URL` to the scratch instance.
4. `alembic upgrade head` should be a no-op (schema already at head) or apply only pending.
5. Run `pytest` smoke subset + `GET /readiness`.
6. Spot-check: one tenant, one call row, one `async_jobs` / `notification_outbox` row.
7. Record date, backup ID, and operator in the ops log.

**Production restore / EXPLAIN not performed against production data.**

## Object storage

- Prefer versioned private buckets (S3 / R2 / MinIO).
- Recordings live under `tenants/{tenant_id}/...` — never public ACLs.
- Backup: enable bucket versioning + cross-region replication **or** documented snapshot tool.
- After DB restore, orphaned objects are acceptable; missing objects with DB rows are handled by retention worker (`exists` then delete / mark deleted).

## Application rollback

- Alembic: prefer forward-fix migrations; do not rely on `downgrade` in production without rehearsal.
- Workers and API must be deployable independently; job handlers must remain backward compatible for in-flight jobs.

## Tenant recovery

1. Identify `tenant_id`.
2. Restore DB (or dedicated DB) to scratch.
3. Verify `tenants`, `tenant_phone_numbers`, `calls`, `async_jobs` for that tenant.
4. Re-point DNS / secrets only after verification.

## What is not configured here

This repository does not provision cloud backup jobs. Operators must configure provider-side backups and re-run the restore verification procedure against staging/managed backups before declaring production DR readiness.
