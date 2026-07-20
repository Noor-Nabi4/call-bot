# Call Bot landing

Public marketing site for Call Bot with SEO metadata, sitemap, and structured data.

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
| `NEXT_PUBLIC_PLAYGROUND_URL` | Voice demo link (default `http://localhost:3000`) |
| `NEXT_PUBLIC_OPS_URL` | Ops / dispatch link (default `http://localhost:3001`) |
| `NEXT_PUBLIC_PLATFORM_API_URL` | Platform API for signup / plans (default `http://localhost:8000`) |

## Routes

| Path | Purpose |
|------|---------|
| `/` | Marketing landing |
| `/pricing` | Voice-minute plans: Starter $99 / Growth $249 (most popular) / Pro $499 + Enterprise |
| `/signup` | Create tenant + admin, redirect to Stripe Checkout (default plan: Growth) |

Signup flow: `/pricing` → `/signup` → Stripe Checkout → ops `/settings/billing`. Subscription activation requires Stripe webhooks on the platform API.

Pricing model: included voice minutes, concurrent calls, and operational feature unlocks (dispatch / tech mobile on Growth+). Per-user pricing is secondary via add-ons.

Platform CORS must allow `http://localhost:3002` (see `OPS_CORS_ORIGINS`).

## SEO surfaces

- `/` — semantic landing + FAQ
- `/sitemap.xml`
- `/robots.txt`
- `/manifest.webmanifest`
- `/opengraph-image` and `/twitter-image`
- JSON-LD: Organization, WebSite, SoftwareApplication, WebPage, FAQPage
