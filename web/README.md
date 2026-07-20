# VoxPilot landing

Public marketing site for VoxPilot — AI Voice Platform for Service Businesses & Call Centers.

Brand assets: see `/branding` (and `public/branding`).

## Run

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3002

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_SITE_URL` | Canonical site origin (required in production for sitemap/OG) |
| `NEXT_PUBLIC_OPS_URL` | Ops console link (default `http://localhost:3001`) |
| `NEXT_PUBLIC_PLATFORM_API_URL` | Platform API for signup / plans (default `http://localhost:8000`) |
| `LIVEKIT_URL` | LiveKit WebSocket URL for embedded voice demo |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | Token minting for `/api/token` |
| `AGENT_NAME` | Agent dispatch name (default `voice-agent`) |
| `METADATA_HMAC_SECRET` | Optional; must match voice-agent if set (signs `source=marketing`) |

## Routes

| Path | Purpose |
|------|---------|
| `/` | Landing: Hero → Voice demo → Features → Industries → Pricing → FAQ → CTA |
| `/signup` | Multi-step onboarding (business, industry, plan, account) → Stripe Checkout |
| `/api/token` | Rate-limited LiveKit token for the embedded browser voice demo |

Signup flow: `/#demo` or `/#pricing` → `/signup` → Stripe Checkout → ops. Subscription activation requires Stripe webhooks on the platform API.

The embedded voice demo is tenant-less (`source=marketing`): visitors talk to a fixed VoxPilot persona with no CRM/tools. Tenant-specific testing lives in Ops → Playground (`/playground`).

The embedded voice demo requires a running `voice-agent` worker plus LiveKit credentials in `web/.env.local`.

## Analytics

Conversion events fire via `track()` (`web/src/lib/analytics.ts`): CustomEvent `voxpilot:analytics` (and legacy `callbot:analytics`), optional `window.dataLayer`, and optional `window.voxpilotTrack` / `window.callbotTrack`.

## SEO surfaces

- `/` — semantic landing + FAQ
- `/sitemap.xml`
- `/robots.txt`
- `/manifest.webmanifest`
- `/opengraph-image` and `/twitter-image`
- JSON-LD: Organization, WebSite, SoftwareApplication, WebPage, FAQPage
