# VoxPilot web

Single Next.js app: public marketing site plus the authenticated operations console.

Brand assets: see `/branding` (and `public/branding`).

## Run

```bash
cd web
cp .env.example .env.local
npm install
npm run dev   # http://localhost:3002
```

Platform API must be running on `:8000` with `SESSION_SECRET` set and CORS allowing `http://localhost:3002`.

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_SITE_URL` | Canonical site origin (required in production for sitemap/OG) |
| `NEXT_PUBLIC_PLATFORM_API_URL` | Platform API for signup, plans, and ops (default `http://localhost:8000`) |
| `LIVEKIT_URL` | LiveKit WebSocket URL for embedded voice demo |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | Token minting for `/api/token` |
| `AGENT_NAME` | Agent dispatch name (default `voice-agent`) |
| `METADATA_HMAC_SECRET` | Optional; must match voice-agent if set (signs `source=marketing`) |

## Public routes

| Path | Purpose |
|---|---|
| `/` | Landing: Hero → Voice demo → Features → Industries → Pricing → FAQ → CTA |
| `/signup` | Multi-step onboarding → Stripe Checkout |
| `/login` | Tenant ops sign-in |
| `/api/token` | Rate-limited LiveKit token for the embedded browser voice demo |

## Ops routes (session cookie)

Dashboard, dispatch, live calls, playground, phones, agents, billing, technician mobile (`/tech`), and the rest of the operations console.

Signup flow: `/#demo` or `/#pricing` → `/signup` → Stripe Checkout → `/settings/billing`. Subscription activation requires Stripe webhooks on the platform API.

The embedded voice demo is tenant-less (`source=marketing`). Tenant-specific testing is **Playground** (`/playground`).

The voice demo requires a running `voice-agent` worker plus LiveKit credentials in `web/.env.local`.

## Bootstrap first admin (internal / legacy)

Public signup on `/signup` is preferred. Internal bootstrap:

```bash
curl -X POST http://localhost:8000/auth/bootstrap \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $INTERNAL_SERVICE_TOKEN" \
  -d '{"tenant_id":"<uuid>","email":"admin@acme.test","password":"password123","name":"Ops Admin"}'
```

Then sign in at `/login` with the tenant slug.

## Analytics

Conversion events fire via `track()` (`web/src/lib/analytics.ts`): CustomEvent `voxpilot:analytics` (and legacy `callbot:analytics`), optional `window.dataLayer`, and optional `window.voxpilotTrack` / `window.callbotTrack`.

## SEO surfaces

- `/` — semantic landing + FAQ
- `/sitemap.xml`
- `/robots.txt`
- `/manifest.webmanifest`
- `/opengraph-image` and `/twitter-image`
- JSON-LD: Organization, WebSite, SoftwareApplication, WebPage, FAQPage
