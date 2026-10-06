# Disaster Recovery

**Date:** 2026-10-06 (Phase 3.1)  
**Status:** Procedure documented.  

```text
RESTORE DRILL NOT EXECUTED
Reason: required infrastructure access unavailable (no non-production Postgres backup credentials in this environment)
RTO: not measured
RPO: not measured
```

## Goals

| Metric | Target (configure per env) |
|--------|----------------------------|
| RPO | ≤ 24h (adjust with continuous WAL archiving) |
| RTO | ≤ 4h for shared-DB fleet restore |

Do **not** claim backups exist until the checklist below is executed in each environment.

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

Keep total under Postgres `max_connections` with headroom.

### Restore verification procedure

1. Provision a scratch Postgres instance.
2. Restore latest backup (and WAL to a known timestamp if using PITR).
3. Set `DATABASE_URL` to the scratch instance.
4. `alembic upgrade head` should be a no-op (schema already at head) or apply only pending.
5. Run `pytest` smoke subset + `GET /readiness`.
6. Spot-check: one tenant, one call row, one `async_jobs` / `notification_outbox` row.
7. Record date, backup ID, and operator in the ops log.

**Production EXPLAIN / restore not performed in CI for this repo.**

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

This repository does not provision cloud backup jobs. Operators must configure provider-side backups and run the restore verification procedure above before declaring production readiness.
