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

## SEO surfaces

- `/` — semantic landing + FAQ
- `/sitemap.xml`
- `/robots.txt`
- `/manifest.webmanifest`
- `/opengraph-image` and `/twitter-image`
- JSON-LD: Organization, WebSite, SoftwareApplication, WebPage, FAQPage
