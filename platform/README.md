# Telephony platform API — multi-tenant Twilio + LiveKit SIP + CRM + Scheduling

## Run locally

```bash
cd platform
cp .env.example .env.local
uv sync
# Postgres required for production; tests use SQLite in-memory
uv run uvicorn callbot_platform.main:app --reload --port 8000
```

## CRM (Phase 3)

Internal routes (require `X-Internal-Token`):

- `POST /internal/crm/customers/lookup`
- `POST /internal/crm/customers/upsert`
- `POST /internal/crm/leads`
- `GET /internal/crm/leads/{id}?tenant_id=`
- `POST /internal/crm/calls/start`
- `POST /internal/crm/calls/end`

Tenant agent settings (admin session cookie):

- `GET|PUT /api/admin/agent-settings` — tenant admin only; scoped to session tenant
- Legacy `GET|PUT /tenants/{id}/agent-settings` — returns `401` (removed)

Internal agent profile (voice-agent / platform token, requires `X-Internal-Token`):

- `GET /internal/tenants/{id}/agent-profile` — fail-closed when missing/inactive
- `GET /internal/tenants/{id}/agent-profile/meta` — version check for cache invalidation
- `PUT /internal/tenants/{id}/agent-settings` — platform override (rate-limited)

## Scheduling (Phase 4)

- `POST /internal/scheduling/slots`
- `POST /internal/scheduling/appointments`
- `GET /internal/scheduling/appointments/{id}?tenant_id=`
- `POST /internal/scheduling/appointments/{id}/reschedule`
- `POST /internal/scheduling/appointments/{id}/cancel`

Availability uses tenant timezone + `tenant_schedule_settings` (default Mon–Fri 09:00–17:00). SMS via Twilio when configured; email rows stay in `notification_outbox`.

Booking an appointment auto-creates a `scheduled` job for the dispatch board.

## Auth + jobs (Phase 5)

Public auth:

- `POST /auth/login` (sets HTTP-only session cookie)
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/bootstrap` (first admin only; requires `X-Internal-Token`)

Session-authenticated ops API (`/api/...`):

- Technicians list/create
- Jobs list/get/create/assign/transition/checklist/notes
- `POST /api/tech/location`

Set `SESSION_SECRET` and `OPS_CORS_ORIGINS` (include `http://localhost:3001`).

## Docs

- Path A / Path B checklist: `../voice-agent/docs/PHASE2_TELEPHONY_CHECKLIST.md`
- CRM checklist: `../voice-agent/docs/PHASE3_CRM_CHECKLIST.md`
- Booking checklist: `../voice-agent/docs/PHASE4_BOOKING_CHECKLIST.md`
- Jobs checklist: `../voice-agent/docs/PHASE5_JOBS_CHECKLIST.md`
- Ops UI: `../ops/README.md`
- LiveKit Twilio SIP: https://docs.livekit.io/telephony/start/providers/twilio/
