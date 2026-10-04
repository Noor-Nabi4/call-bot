# Call & Flow SEO Audit

Date: 2026-10-05  
Site: https://callandflow.com/  
App: `web/` (Next.js App Router)

## Scope of this refinement

Commercial SEO refinement on top of the existing P0 foundation. Architecture, metadata helpers, JSON-LD builders, visual system, CTAs, and existing slugs are preserved. No new keyword doorway routes.

## Route decisions (no new doorways)

| Proposed route | Decision | Covered by |
|---|---|---|
| `/ai-phone-agent` | Do not create | `/ai-voice-agents` |
| `/ai-answering-service` | Do not create | `/ai-receptionist` + `/use-cases/call-answering` |
| `/ai-call-answering` | Do not create | `/use-cases/call-answering` |
| `/ai-receptionist-for-small-business` | Do not create | `/ai-receptionist` |
| `/use-cases` hub | Create | Indexable hub mirroring `/industries` |

## Cannibalization map

| Pair | Distinct intent |
|---|---|
| Homepage vs `/ai-receptionist` | Platform overview / AI voice agents category vs front-desk AI receptionist product |
| `/ai-receptionist` vs `/use-cases/call-answering` | Product category (receptionist) vs workflow (never-miss-a-call / overflow coverage) |
| `/ai-voice-agents` vs `/use-cases/sales-calls` | Voice-agent platform vs inbound sales opportunity handling |
| Industry landers vs industry blog posts | Commercial conversion pages vs informational/support articles |
| `/use-cases` hub vs `/use-cases/[slug]` | Index of use cases vs deep workflow landers |

## Page inventory (primary keywords)

### Core

| URL | Primary keyword | Title | H1 | Indexable | Schema |
|---|---|---|---|---|---|
| `/` | AI voice agents | AI Voice Agents & AI Receptionist for Businesses \| Call & Flow | AI Voice Agents for Your Business | yes | Org/WebSite/SoftwareApplication + Home HowTo/ItemList/WebPage + FAQ |
| `/ai-receptionist` | AI receptionist | AI Receptionist for Small Business & Phone Answering | AI Receptionist for Your Business | yes | WebPage, Breadcrumb, FAQ |
| `/ai-voice-agents` | AI voice agents | AI Voice Agents Platform for Business Phone Automation | AI Voice Agents for Business Phone Automation | yes | WebPage, Breadcrumb, FAQ |
| `/pricing` | AI voice agent pricing | AI Voice Agent & AI Receptionist Pricing | (pricing H1) | yes | WebPage, Breadcrumb, FAQ, Product/Offer |
| `/industries` | AI voice agents by industry | AI Voice Agents by Industry | AI Voice Agents Built for Your Industry | yes | WebPage, Breadcrumb |
| `/use-cases` | AI voice agent use cases | AI Voice Agent Use Cases for Business Phone Calls | AI Voice Agent Use Cases | yes | WebPage, Breadcrumb |
| `/blog` | AI voice agents resources | Resources on AI Voice Agents… | Call & Flow Resources | yes | WebPage, Breadcrumb |

### Industries

| URL | Primary keyword |
|---|---|
| `/industries/hvac` | AI receptionist for HVAC companies |
| `/industries/plumbing` | AI receptionist for plumbers |
| `/industries/roofing` | AI receptionist for roofing companies |
| `/industries/electricians` | AI receptionist for electricians |
| `/industries/healthcare` | AI receptionist for healthcare |
| `/industries/dental` | AI receptionist for dental offices |
| `/industries/legal` | AI receptionist for law firms |
| `/industries/real-estate` | AI receptionist for real estate |
| `/industries/restaurants` | AI phone answering for restaurants |
| `/industries/insurance` | AI receptionist for insurance agencies |
| `/industries/home-services` | AI receptionist for home services |
| `/industries/call-centers` | AI voice agents for call centers |

### Use cases

| URL | Primary keyword |
|---|---|
| `/use-cases/appointment-booking` | AI appointment booking |
| `/use-cases/lead-qualification` | AI lead qualification |
| `/use-cases/customer-support` | AI customer support voice agent |
| `/use-cases/call-answering` | AI call answering service |
| `/use-cases/sales-calls` | AI sales voice agent |

## Technical systems (unchanged conventions)

- Metadata: `buildPageMetadata()` in `src/lib/metadata.ts`
- Canonicals: path-relative via `metadataBase` / `NEXT_PUBLIC_SITE_URL` → `https://callandflow.com`
- Sitemap: `src/app/sitemap.ts` from `PUBLIC_MARKETING_ROUTES` + industry/use-case/blog registries
- Robots: `src/app/robots.ts` + `ROBOTS_DISALLOW` (ops/auth only)
- JSON-LD: existing helpers only; no Review/AggregateRating; FAQ schema only with visible FAQs

## Internal linking strategy

- Contextual links inside copy over giant lists
- Natural anchor variation
- Hub cards for discovery; RelatedLinks for next steps
- Blog articles support commercial pages (do not replace them)

## Remaining external / ops tasks

1. Set production `NEXT_PUBLIC_SITE_URL=https://callandflow.com`
2. Verify Google Search Console property and submit `https://callandflow.com/sitemap.xml`
3. URL Inspection for key commercial URLs; request indexing only when needed
4. Do not claim indexed/ranking status without GSC evidence
5. Validate FAQ rich results after deploy
6. Enforce www/non-www and trailing-slash at CDN to match canonical host
