# Production Deployment

**Date:** 2026-10-06 (final production readiness verification)

## Processes

| Process | Command |
|---------|---------|
| API | `uvicorn callbot_platform.main:app` |
| Outbox worker | `python -m callbot_platform.workers.run_outbox` |
| Job worker | `python -m callbot_platform.workers.run_jobs` |
| Voice agent | voice-agent worker (LiveKit Agents) |

## Required production environment variables

```text
ENVIRONMENT=production
REQUIRE_CALL_SCOPE=true
METADATA_HMAC_SECRET=
INTERNAL_SERVICE_TOKEN=
SESSION_SECRET=
CREDENTIALS_ENCRYPTION_KEY=
DATABASE_URL=postgresql+psycopg://...
DB_POOL_SIZE=
DB_MAX_OVERFLOW=
DB_POOL_TIMEOUT=
DB_POOL_RECYCLE=
DB_POOL_PRE_PING=

# Object storage
OBJECT_STORAGE_BACKEND=s3   # or r2 / minio / filesystem (dev only)
OBJECT_STORAGE_ROOT=        # filesystem only
OBJECT_STORAGE_MAX_UPLOAD_BYTES=52428800
OBJECT_STORAGE_SIGNED_URL_TTL_SECONDS=300
RECORDING_RETENTION_DAYS=30
S3_BUCKET=
S3_REGION=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_ENDPOINT_URL=            # required for R2 / MinIO
S3_FORCE_PATH_STYLE=        # often true for MinIO

# Workers
OUTBOX_LEASE_SECONDS=
JOB_LEASE_SECONDS=
# plus OUTBOX_* / JOB_* poll / batch settings from Settings

# Providers
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
LIVEKIT_SIP_HOST=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
```

### Live S3 verification gate (staging only)

```text
S3_INTEGRATION_TEST=1
S3_BUCKET=
S3_REGION=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_ENDPOINT_URL=            # if R2/MinIO
OBJECT_STORAGE_BACKEND=s3
```

Never commit secret values.

## Verification notes (this environment)

| Item | Status |
|------|--------|
| Staging fleet / managed backup / live S3 | NOT AVAILABLE |
| `REQUIRE_CALL_SCOPE=true` in `platform/.env.production.example` | VERIFIED |
| `REQUIRE_CALL_SCOPE=true` written by `deploy/install.sh` | VERIFIED (fixed this gate) |
| Compose `REQUIRE_CALL_SCOPE=true` + `/readiness` healthcheck | VERIFIED (fixed this gate) |
| Production/Supabase | NOT TOUCHED |

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

Defaults: `DB_POOL_SIZE=5` + `DB_MAX_OVERFLOW=10` → **15 connections per process**.

Recommended staging check before scale-out: confirm Postgres `max_connections` ≥ fleet total + ≥20% headroom.

**Note:** `docker-compose.production.yml` currently runs API + web only — outbox/job workers must be operated as separate processes (`python -m callbot_platform.workers.run_outbox` / `run_jobs`).
