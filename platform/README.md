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

Tenant agent settings: `GET|PUT /tenants/{id}/agent-settings`

## Scheduling (Phase 4)

- `POST /internal/scheduling/slots`
- `POST /internal/scheduling/appointments`
- `GET /internal/scheduling/appointments/{id}?tenant_id=`
- `POST /internal/scheduling/appointments/{id}/reschedule`
- `POST /internal/scheduling/appointments/{id}/cancel`

Availability uses tenant timezone + `tenant_schedule_settings` (default Mon–Fri 09:00–17:00). SMS via Twilio when configured; email rows stay in `notification_outbox`.

## Docs

- Path A / Path B checklist: `../voice-agent/docs/PHASE2_TELEPHONY_CHECKLIST.md`
- CRM checklist: `../voice-agent/docs/PHASE3_CRM_CHECKLIST.md`
- Booking checklist: `../voice-agent/docs/PHASE4_BOOKING_CHECKLIST.md`
- LiveKit Twilio SIP: https://docs.livekit.io/telephony/start/providers/twilio/
