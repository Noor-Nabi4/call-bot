# Call Bot Ops

Tenant-scoped operations console: dashboard overview, dispatch board, and
technician mobile UI.

Premium ops product: warm-gray canvas, white surfaces, teal brand `#1f6f5b`,
IBM Plex Sans/Mono, left sidebar navigation. Shared UI under `src/components/ui/`
and `src/components/ops/`.

## Routes

| Path | Purpose |
|------|---------|
| `/dashboard` | Default landing after login (ops overview) |
| `/dispatch` | Kanban job assignment workspace |
| `/board` | Redirects to `/dispatch` (compat) |
| `/live` | Active calls (auto-refresh) |
| `/supervisor` | Supervisor snapshot (live + recent + handoffs) |
| `/queue` | Handoff follow-up queue |
| `/calls` | Call history |
| `/agents` | Multi-profile agent builder |
| `/marketplace` | One-click industry agent installs |
| `/agents/[id]/flow` | Ordered call-flow steps for an agent |
| `/metrics` | Call analytics |
| `/settings` | Team, retention, audit |
| `/settings/automations` | Event-driven automation rules |
| `/settings/api-keys` | Public /v1 API keys |
| `/settings/branding` | White-label product name, logo, colors |
| `/settings/billing` | SaaS subscription status + Stripe Customer Portal |
| `/settings/assistant` | Voice assistant profile |
| `/tech` | Technician mobile jobs |

## Run

```bash
cd ops
cp .env.example .env.local
npm install
npm run dev   # http://localhost:3001
```

Platform API must be running on `:8000` with `SESSION_SECRET` set and CORS allowing `http://localhost:3001`.

## Signup (preferred)

Public signup lives on the marketing site (`web/` → `/pricing` → `/signup`). After Stripe Checkout, users land on `/settings/billing`. Plan activation requires Stripe webhooks — the success redirect alone does not activate.

## Bootstrap first admin (internal / legacy)

```bash
curl -X POST http://localhost:8000/auth/bootstrap \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $INTERNAL_SERVICE_TOKEN" \
  -d '{"tenant_id":"<uuid>","email":"admin@acme.test","password":"password123","name":"Ops Admin"}'
```

Then sign in at `/login` with the tenant slug.
