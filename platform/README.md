# VoxPilot Platform API

Telephony platform API — multi-tenant Twilio + LiveKit SIP + CRM + Scheduling.
Python package namespace remains `callbot_platform` for compatibility.

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

- `POST /auth/signup` — create tenant + admin + Stripe Checkout Session (sets session cookie; **does not** activate plan)
- `POST /auth/login` (sets HTTP-only session cookie)
- `POST /auth/logout`
- `GET /auth/me`
- `PUT /auth/me`
- `POST /auth/bootstrap` (first admin only; requires `X-Internal-Token`)

SaaS billing (platform Stripe account — **not** Connect):

- `GET /billing/plans` — public catalog from code: Starter ($99 / 250 min), Growth ($249 / 800 min, most popular), Pro ($499 / 2,000 min), plus Enterprise (contact sales), trial, number pricing, and add-ons. Each paid plan includes `entitlements` (minutes, concurrency, numbers, users, knowledge, feature flags).
- `GET /billing/subscription` — admin session (includes plan entitlements)
- `GET /billing/usage` — current UTC calendar-month voice minutes + resource usage vs plan limits
- `POST /billing/checkout` — resume Checkout when incomplete/canceled
- `POST /billing/portal` — Stripe Customer Portal (payment method / cancel)
- `POST /billing/webhooks/stripe` — signature-verified webhooks (source of truth for activation)

Hard entitlement enforcement (SaaS tenants with a plan row): team seats, phone numbers, and knowledge documents cannot exceed plan limits. Voice minutes are soft — tracked and overage estimated; Stripe metered overage invoicing is not yet wired.

Internal COGS (admin only — estimated infrastructure cost, not customer invoices):

- `GET /api/admin/cogs/summary?period=this_month|last_month|today|7d|30d|custom` — KPIs, daily COGS series, channel/transfer breakdown
- `GET /api/admin/cogs/scenarios` — modeled 1,000 / 10,000 / 100,000 minutes, OpenAI sensitivity, Ship vs Scale
- `GET /api/admin/cogs/calls` — paginated per-call COGS (channel / transfer / call_id filters)
- `GET /api/admin/cogs/calls/{call_id}` — call COGS detail including OpenAI usage snapshot
- Ops UI: `/settings/cogs` (admin only)

Rates are configured via `COGS_*` env vars (see `.env.example`). OpenAI cost prefers Realtime token usage from the voice-agent when present; otherwise uses `COGS_OPENAI_PER_MINUTE_USD`. Vendor minutes for COGS are fractional (`billable_seconds / 60`); customer billable minutes remain ceil-based and unchanged. Phone rental / SMS / LiveKit fixed monthly fees are reported separately from variable voice-minute COGS.

Ops: `/settings/billing` shows usage; `/settings/team` manages invite / role / deactivate.

Plans are **not** registered as Stripe Products/Prices. Checkout uses inline `price_data` from `billing/plans.py`. Only `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` are required.

Set `SESSION_SECRET` and `OPS_CORS_ORIGINS` (local `http://localhost:3002`; production `https://voxpilot.techverseo.com`).

Configure Stripe (platform account):

1. Set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` (platform Stripe account)
2. Webhook endpoint → `https://api.voxpilot.techverseo.com/billing/webhooks/stripe` (production) or `/billing/webhooks/stripe` on the API host for `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, `invoice.payment_failed`
3. Customer Portal: payment method update + cancellation (plan switching in Portal needs registered Prices — not used; upgrades go through new Checkout with `price_data`)

Do **not** reuse Stripe Connect keys here. Tenant merchant payments (Phase 6) are separate.

`POST /tenants` requires `X-Internal-Token`. Public onboarding uses `/auth/signup`.

Session-authenticated ops API (`/api/...`):

- Technicians list/create
- Jobs list/get/create/assign/transition/checklist/notes
- `POST /api/tech/location`

Gated routes require subscription status `trialing` or `active` (legacy tenants with no subscription row and `tenant.status=active` remain entitled).

## Docs

- Path A / Path B checklist: `../voice-agent/docs/PHASE2_TELEPHONY_CHECKLIST.md`
- CRM checklist: `../voice-agent/docs/PHASE3_CRM_CHECKLIST.md`
- Booking checklist: `../voice-agent/docs/PHASE4_BOOKING_CHECKLIST.md`
- Jobs checklist: `../voice-agent/docs/PHASE5_JOBS_CHECKLIST.md`
- Web (marketing + ops): `../web/README.md`
- LiveKit Twilio SIP: https://docs.livekit.io/telephony/start/providers/twilio/
