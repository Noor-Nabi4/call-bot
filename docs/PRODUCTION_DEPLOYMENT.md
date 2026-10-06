# Production Deployment

**Date:** 2026-10-06 (Phase 3.1)

## Processes

| Process | Command |
|---------|---------|
| API | `uvicorn callbot_platform.main:app` |
| Outbox worker | `python -m callbot_platform.workers.run_outbox` |
| Job worker | `python -m callbot_platform.workers.run_jobs` |
| Voice agent | voice-agent worker (LiveKit Agents) |

## Required production settings

```text
ENVIRONMENT=production
REQUIRE_CALL_SCOPE=true
METADATA_HMAC_SECRET=...
INTERNAL_SERVICE_TOKEN=...
SESSION_SECRET=...
CREDENTIALS_ENCRYPTION_KEY=...
DATABASE_URL=postgresql+psycopg://...
DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT / DB_POOL_RECYCLE / DB_POOL_PRE_PING
OBJECT_STORAGE_BACKEND=s3   # or r2 / minio
S3_BUCKET=
S3_REGION=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_ENDPOINT_URL=            # required for R2/MinIO
S3_FORCE_PATH_STYLE=        # often true for MinIO
OBJECT_STORAGE_MAX_UPLOAD_BYTES=
RECORDING_RETENTION_DAYS=
OUTBOX_* / JOB_* / JOB_LEASE_SECONDS / OUTBOX_LEASE_SECONDS
STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET
LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET / LIVEKIT_SIP_HOST
TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN
```

Never commit secret values.

## Smoke checklist

1. `alembic upgrade head`
2. Start API → `GET /liveness` → `GET /readiness`
3. Start outbox + job workers (logs show starting)
4. Create/test tenant via internal API
5. Exercise CRM call start/end with `X-Call-Scope`
6. Confirm async job dequeue for a provision/release
7. Put/get recording via configured storage
8. Stripe webhook signature rejection with bad sig
9. SIGTERM workers → graceful stop, no stuck `running` beyond lease
10. Cross-tenant IDOR attempt → 403/404

## Connection budget

```text
total ≈ API_replicas×(pool+overflow)
      + outbox_replicas×(pool+overflow)
      + job_replicas×(pool+overflow)
      + admin
```

Keep under Postgres `max_connections` with headroom.
