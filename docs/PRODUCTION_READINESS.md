# Production Readiness Checklist (Phase 3)

## Security

- [x] tenant isolation (server-side `tenant_id` filters + TenantContext)
- [x] call-scoped authorization on CRM / scheduling / knowledge / handoff internals
- [x] secrets via env (no hardcoded provider keys)
- [x] signed object URLs (S3 presign; filesystem local URI for dev)
- [x] Stripe webhook signature + event-id idempotency
- [x] deterministic job idempotency keys
- [x] REQUIRE_CALL_SCOPE required in production settings
- [x] no secrets in structured worker logs (keys/tokens redacted by omission)

## Database

- [x] migration `0022_phase3_async_jobs`
- [x] indexes on `async_jobs` dequeue / tenant / type
- [x] connection pools bounded (`DB_POOL_*`)
- [x] tenant routing / dedicated engine cache (Phase 1/2)
- [x] backup strategy documented (`docs/DISASTER_RECOVERY.md`)
- [ ] restore procedure **executed** in staging/prod (operator task)

## Workers

- [x] graceful SIGTERM shutdown
- [x] leases + reclaim
- [x] retries + exponential backoff
- [x] DLQ + admin replay
- [x] metrics (structured)
- [x] TenantContext in workers

## External Providers

- [x] Twilio purchase saga (async job)
- [x] LiveKit connect saga (async job)
- [x] Stripe signup saga (async job)
- [x] provider failures → retry / DLQ / partial phone state
- [ ] Live provider chaos testing in staging (operator task)

## Storage

- [x] S3-compatible backend (`OBJECT_STORAGE_BACKEND=s3|r2|minio`)
- [x] private objects / tenant-scoped keys
- [x] signed URLs
- [x] retention cleanup idempotent for missing objects
- [x] upload size limit

## Operations

- [x] `/liveness` vs `/readiness`
- [x] logging + metrics
- [x] load-testing methodology doc
- [x] disaster recovery doc
- [x] worker / saga runbooks

## Explicit remaining risks

- Production EXPLAIN ANALYZE not performed (no staging dataset in CI).
- Backups not verified in this environment.
- boto3 required only when using S3 backend.
- Release/subaccount paths still perform some provider I/O in request handlers (short-lived; purchase/connect/signup sagas are the critical dual-write fixes).
