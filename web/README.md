# Call & Flow web

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
| `NEXT_PUBLIC_SITE_URL` | Canonical site origin (`https://callandflow.com` in production) |
| `NEXT_PUBLIC_PLATFORM_API_URL` | Platform API (`https://api.callandflow.com` in production) |
| `LIVEKIT_URL` | LiveKit WebSocket URL for embedded voice demo |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | Token minting for `/api/token` |
| `AGENT_NAME` | Agent dispatch name (default `voice-agent`) |
| `METADATA_HMAC_SECRET` | Optional; must match voice-agent if set (signs `source=marketing`) |

## Public marketing routes

| Path | Purpose |
|---|---|
| `/` | Homepage: hero, demo, features, industries, pricing preview, FAQ |
| `/ai-voice-agents` | AI voice agents product page |
| `/ai-receptionist` | AI receptionist product page |
| `/pricing` | Full plans, trial, numbers, add-ons (live catalog) |
| `/industries` | Industry hub |
| `/industries/[slug]` | Industry landers (HVAC, plumbing, healthcare, …) |
| `/use-cases/[slug]` | Use-case landers (booking, qualification, support, …) |
| `/blog`, `/blog/[slug]` | Resources / articles |
| `/signup` | Multi-step onboarding → Stripe Checkout |
| `/login` | Tenant ops sign-in (`noindex`) |
| `/api/token` | Rate-limited LiveKit token for the embedded browser voice demo |

## Ops routes (session cookie)

Dashboard, dispatch, live calls, playground, phones, agents, billing, technician mobile (`/tech`), and the rest of the operations console. These are disallowed in `robots.txt`.

Signup flow: `/pricing` or `/#demo` → `/signup` → Stripe Checkout → `/settings/billing`. Subscription activation requires Stripe webhooks on the platform API.

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

Conversion events fire via `track()` (`web/src/lib/analytics.ts`): CustomEvent `callandflow:analytics` (legacy `voxpilot:analytics` / `callbot:analytics`), optional `window.dataLayer`, and optional `window.callandflowTrack` / `window.voxpilotTrack` / `window.callbotTrack`.

## SEO

- Metadata helper: `src/lib/metadata.ts` (`buildPageMetadata`)
- Content registries: `src/lib/marketing/*`
- `/sitemap.xml`, `/robots.txt`, `/manifest.webmanifest`
- `/opengraph-image` and `/twitter-image`
- JSON-LD: Organization, WebSite, SoftwareApplication, WebPage, FAQPage, BreadcrumbList, Product/Offer, Article
- Docs: `SEO-AUDIT.md`, `SEO-ROADMAP.md`

## Visuals

- Product mockups / workflow diagrams: `src/components/landing/visuals/*`
- Visual config: `src/lib/marketing/visuals.ts`
- Organized photos: `public/images/{hero,product,industries,use-cases}/`
- Asset notes: `VISUAL-ASSETS.md`
