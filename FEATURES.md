# Call & Flow — Complete Feature Documentation

**Product:** Call & Flow  
**Site:** https://callandflow.com  
**API:** https://api.callandflow.com  

This document describes **features that exist in the product codebase today**. It does not invent integrations, certifications, customer counts, benchmarks, or future roadmap items as shipped capabilities.

Related docs:

- Phased product plan: [`TASKS.md`](./TASKS.md)
- Platform API: [`platform/README.md`](./platform/README.md)
- Web (marketing + ops): [`web/README.md`](./web/README.md)
- Voice agent: [`voice-agent/README.md`](./voice-agent/README.md)
- Production deploy: [`deploy/README.md`](./deploy/README.md)

---

## 1. Product overview

Call & Flow is a **multi-tenant AI voice platform** for service businesses and call centers. It combines:

| Layer | Role |
|---|---|
| **Voice agent** | LiveKit worker + OpenAI Realtime speech-to-speech |
| **Platform API** | FastAPI: telephony, CRM, scheduling, jobs, knowledge, billing, handoff, automations |
| **Web app** | Public marketing site + authenticated ops console (Next.js) |

Typical flow:

```text
Caller (phone or browser demo)
  → LiveKit room (SIP or WebRTC)
  → Voice agent (tenant resolve → Agent Profile → Realtime session)
  → Platform tools (CRM / booking / knowledge / handoff)
  → Ops console (calls, customers, appointments, dispatch, settings)
```

---

## 2. Surfaces

### 2.1 Public marketing site (`web/`)

| Route | Purpose |
|---|---|
| `/` | Homepage: hero, voice demo, features, industries, pricing preview, FAQ |
| `/ai-voice-agents` | Platform / voice-agent product pillar |
| `/ai-receptionist` | AI receptionist product pillar |
| `/pricing` | Live plan catalog, trial, numbers, add-ons |
| `/industries`, `/industries/[slug]` | Industry hub + landers |
| `/use-cases`, `/use-cases/[slug]` | Use-case hub + landers |
| `/blog`, `/blog/[slug]` | Resources / articles |
| `/signup` | Multi-step onboarding → Stripe Checkout |
| `/login` | Tenant ops sign-in (`noindex`) |
| `/api/token` | Rate-limited LiveKit token for marketing voice demo |

SEO systems: sitemap, robots, canonicals, Open Graph / Twitter images, JSON-LD (Organization, WebSite, SoftwareApplication, WebPage, FAQ, Breadcrumb, Product/Offer, Article). No fake Review/AggregateRating schema.

### 2.2 Operations console (session cookie)

Authenticated ops UI (disallowed in `robots.txt`), including:

| Area | Routes (examples) |
|---|---|
| Work | Dashboard, Dispatch, Customers, Live, Supervisor, Queue, Calls, Appointments, Metrics |
| AI | Playground, Agents, Marketplace, Phones, Knowledge, Handoff |
| Admin | Settings, Team, Billing, COGS, Automations, API keys, Branding, Tech |
| Field | Technician mobile (`/tech`) |

### 2.3 Platform API (`platform/`)

Public, session, internal, billing, and `/v1` API-key surfaces. See [`platform/README.md`](./platform/README.md).

### 2.4 Voice agent worker (`voice-agent/`)

Production voice-only LiveKit agent using OpenAI Realtime. Runs as a worker (console / dev / production start).

---

## 3. Multi-tenancy & identity

- Each customer is a **tenant** with its own data, numbers, agents, knowledge, and users.
- Voice calls **fail closed** if tenant / Agent Profile cannot be resolved.
- Phone numbers can map to a specific `agent_profile_id` (or tenant default).
- Tools never accept a client-supplied `tenant_id` override.
- Session auth for ops; `X-Internal-Token` for internal platform/voice routes.
- First admin can be bootstrapped via `POST /auth/bootstrap` (internal); public path is `/signup`.

---

## 4. Voice AI engine

### 4.1 Runtime

- **LiveKit Agents** session in a LiveKit room
- **OpenAI Realtime** speech-to-speech (not a separate STT→LLM→TTS pipeline as the primary production path)
- Semantic VAD / turn detection and barge-in (interruptions)
- Per-call state (`CallState` / `CallFacts`) — no invented long-term memory beyond platform data
- Structured logs and metrics (tenant, profile version, tool outcomes)

### 4.2 Agent Profile

After tenant resolve, the agent loads a versioned **Agent Profile** from the Platform API:

- Business identity (name, language, services context)
- Voice preference
- Custom instructions / restricted topics / handoff rules
- `enabled_tools` groups: `crm`, `scheduling`, `knowledge`, `handoff`, `sms`
- Optional ordered **call flow** compiled into prompt instructions (`prompt-compose-v4`)
- Short-lived profile cache (in-memory, or shared Redis when `REDIS_URL` is set)

Marketing/browser demo uses a constrained tenant-less profile (`source=marketing`). Tenant-specific testing is **Playground**.

### 4.3 Voice tools (what the agent can do on a call)

**CRM**

- `get_call_context` — caller/called numbers, business name, SIP flag
- `lookup_customer_by_phone`
- `create_or_update_customer`
- `create_lead`

**Scheduling**

- `get_available_slots` — real availability only (no invented times)
- `book_appointment`
- `reschedule_appointment`
- `cancel_appointment`

**Knowledge**

- `search_knowledge` — tenant (+ profile-scoped) curated articles; injection-filtered retrieval

**Handoff**

- `request_human_handoff` — warm or cold transfer per tenant handoff config, with escalation reasons (billing dispute, emergency, abuse, caller request, complex, other). Failed transfer offers callback rather than claiming success.

Tool groups are gated by the active profile’s `enabled_tools`.

### 4.4 Prompt composition

Versioned composition stacks:

1. Platform safety rules  
2. Voice style / concision policy  
3. Tenant identity, rules, preferences  
4. Optional call-flow steps  
5. Tool usage rules  
6. Live call context  

Default spoken style: answer first; keep responses short unless detail is needed.

---

## 5. Agent profiles, templates & marketplace

Ops: `/agents`, `/marketplace`

| Feature | Detail |
|---|---|
| Multiple agent profiles per tenant | Create, edit, delete, set default |
| Industry / role templates | Apply starter templates (receptionist, support, sales-style configs, industry packs) |
| Marketplace install | Install packaged agent templates into the tenant |
| Per-number assignment | Assign a profile to a phone number |
| Call-flow builder | Linear call-flow steps compiled into agent instructions |
| Tool gating | Enable/disable CRM, scheduling, knowledge, handoff, SMS tool groups |

---

## 6. Telephony

Ops: `/phones`  
Platform: phone connect / purchase / verify routes under admin + internal APIs

| Feature | Detail |
|---|---|
| Connect existing number | Bring your own Twilio number / trunk path (Path A/B) |
| Platform purchase | Buy numbers through platform inventory (when configured) |
| Release number | Release a platform-provisioned number |
| Twilio subaccount | Per-tenant Twilio subaccount provisioning path |
| Verification | Number verification start/confirm flows |
| Trunk confirm | Confirm LiveKit SIP trunk wiring |
| Test call | Admin-triggered test call from ops |
| DID → tenant resolve | Fail-closed SIP/DID resolution for inbound calls |

LiveKit media can run on **LiveKit Cloud** or a **self-hosted SFU** (deploy installer supports both).

---

## 7. CRM & call records

Ops: `/customers`, `/calls`, `/live`, `/supervisor`, `/queue`

| Feature | Detail |
|---|---|
| Customer lookup / upsert | By phone and structured fields |
| Leads | Create and fetch lead records from voice tools / API |
| Call start / end | Internal CRM call lifecycle for the voice agent |
| Call history | Ops list/detail; quality tagging |
| Live view | Live call monitoring surface |
| Supervisor | Supervisor ops view |
| Follow-up queue | Claim / complete queue items after handoff or automation |
| Metrics | Call and booking-oriented metrics dashboard |

Internal CRM routes require `X-Internal-Token`. Ops CRM views use the authenticated admin session.

---

## 8. Appointment booking (scheduling)

Ops: `/appointments`  
Voice tools + internal scheduling API

| Feature | Detail |
|---|---|
| Availability slots | Based on tenant timezone + schedule settings (default Mon–Fri 09:00–17:00) |
| Book / reschedule / cancel | Real appointment records |
| Notifications | SMS via Twilio when configured; email rows via notification outbox |
| Job handoff | Booking an appointment can auto-create a `scheduled` job on the dispatch board |

The agent must fetch real slots before offering times — invented availability is explicitly disallowed in tool design.

---

## 9. Jobs, dispatch & technician mobile

Ops: `/dispatch` (also `/board`), `/tech`  
Plan-gated: dispatch / tech mobile entitlements on Growth+ (see plans)

| Feature | Detail |
|---|---|
| Jobs CRUD | Create, list, get jobs |
| Assign technician | Assign jobs to techs |
| Status transitions | Move jobs through workflow states |
| Checklist + notes | Job checklist updates and notes |
| Technicians | List/create technicians |
| Dispatch board | Visual ops board for field work |
| Tech mobile | Technician-focused jobs UI |
| Location ping | `POST /api/tech/location` for technician location updates |

---

## 10. Knowledge base

Ops: `/knowledge`

| Feature | Detail |
|---|---|
| Curated articles | Create / update / delete FAQ and policy content |
| Tenant + profile scope | Search includes tenant-wide and active-profile articles |
| Voice search tool | `search_knowledge` during live calls |
| Safety filtering | Retrieved content filtered against prompt-injection patterns |
| Isolation | Cross-tenant leakage prevented (covered by automated tests) |
| Plan limits | Knowledge document caps by plan entitlement |

---

## 11. Human handoff

Ops: `/handoff`

| Feature | Detail |
|---|---|
| Escalation phone + mode | Configure where humans receive transfers |
| Warm transfer | LiveKit warm-transfer path (when trunk configured) |
| Cold transfer | SIP REFER-style cold transfer |
| Confirmation gate | Tool requires caller confirmation / valid reason |
| Failure handling | Offer callback if transfer cannot complete |
| Advanced handoff | Plan entitlement on Growth+ (`advanced_handoff_enabled`) |
| Follow-up queue | Handoff can feed ops queue for human follow-up |

---

## 12. Automations & webhooks

Ops: `/settings/automations`

**Triggers**

- `call.ended`
- `call.handoff_requested`
- `appointment.created`

**Actions**

- `write_audit`
- `create_follow_up_job`
- `post_webhook` (signed delivery; `X-CallAndFlow-*` headers, plus legacy `X-Callbot-*`)

Rules are tenant-scoped, enable/disable, and audited.

---

## 13. Billing, plans & usage

Ops: `/settings/billing`, `/settings/cogs`  
Public: `/pricing`, `/signup`

### 13.1 Plans (code catalog)

| Plan | List price (USD/mo) | Minutes | Concurrency | Numbers | Users | Knowledge |
|---|---|---|---|---|---|---|
| **Starter** | $99 | 250 | 1 | 1 | 3 | 10 |
| **Growth** | $249 | 800 | 3 | 3 | 10 | 100 |
| **Pro** | $499 | 2,000 | 10 | 10 | 25 | 500 |
| **Enterprise** | Contact sales | Custom | Custom | Custom | Custom | Custom |

Trial offer (catalog): **14 days**, **50 voice minutes**, **1 concurrent call**, browser voice testing, **no credit card required** for trial start.

Number pricing:

- Connect existing: no extra platform connection fee (customer pays their Twilio/carrier costs)
- Platform purchase: platform number fees as defined in billing catalog

Overage per-minute rates are defined per plan in code (soft tracking / estimate; Stripe metered overage invoicing is **not fully wired** as of this doc).

### 13.2 Billing features

- Stripe Checkout with inline `price_data` (no pre-registered Stripe Products required)
- Stripe Customer Portal (payment method / cancel)
- Signature-verified Stripe webhooks (activation source of truth)
- Subscription + usage endpoints for ops
- Hard entitlement enforcement for seats, phone numbers, and knowledge docs
- Voice minutes tracked (soft / overage estimate)

### 13.3 Internal COGS (admin)

Ops: `/settings/cogs`

- Period summaries, scenarios, per-call COGS
- OpenAI usage snapshot when available from the voice agent
- Configured via `COGS_*` environment variables  
This is **internal cost estimation**, not customer invoices.

---

## 14. Auth, team & retention

| Feature | Detail |
|---|---|
| Signup | `POST /auth/signup` — tenant + admin + Checkout session |
| Login / logout / me | Session cookie auth |
| Profile update | `PUT /auth/me` |
| Team invite / roles | Ops Settings → Team (admin / dispatcher / technician patterns) |
| Deactivate users | Team management |
| Subscription gate | Many ops routes require `trialing` or `active` (legacy active tenants without a subscription row remain entitled) |
| Retention settings | Configurable retention days with audit |
| Audit log | Admin-visible audit of sensitive writes |

---

## 15. Branding

Ops: `/settings/branding`

- Product name, logo URL, primary/accent colors, support email
- White-label ops chrome for the tenant workspace  
(Custom domains are not documented as a shipped self-serve feature here.)

---

## 16. Public API & API keys

Ops: `/settings/api-keys`  
Public API prefix: `/v1`

| Feature | Detail |
|---|---|
| API key management | Create / list / delete keys (admin) |
| `/v1/customers` | Read customers (API key) |
| `/v1/calls` | Read calls (API key) |

Scope is intentionally limited today — expand via roadmap, not assumed present.

---

## 17. Ops console feature map (by screen)

| Screen | What operators can do |
|---|---|
| **Dashboard** | High-level ops snapshot / charts |
| **Dispatch / Board** | Manage field jobs visually |
| **Customers** | Browse/manage customer records |
| **Live** | Monitor live call activity |
| **Supervisor** | Supervisory call-center style view |
| **Queue** | Claim/complete follow-up work |
| **Calls** | Call history and quality tags |
| **Appointments** | View/manage bookings |
| **Metrics** | Usage and operational analytics |
| **Playground** | Tenant-scoped browser voice testing |
| **Agents** | Profiles, call flows, templates |
| **Marketplace** | Install agent packs |
| **Phones** | Connect/purchase/verify/test numbers |
| **Knowledge** | Curate FAQ / policy articles |
| **Handoff** | Escalation destination and transfer mode |
| **Settings** | Tenant admin settings |
| **Team** | Invite and manage users |
| **Billing** | Plan, usage, Stripe portal |
| **COGS** | Internal profitability estimates |
| **Automations** | Trigger → action rules |
| **API keys** | External API credentials |
| **Branding** | White-label chrome |
| **Tech** | Technician job list / mobile workflow |

---

## 18. Marketing product claims (aligned to real capabilities)

These are the commercial themes the marketing site is allowed to emphasize because the product supports them:

1. **AI receptionist** — answer, greet, capture intent, route workflows  
2. **AI voice agents platform** — configurable agent profiles + tools  
3. **Appointment booking by phone** — real slot fetch + book/reschedule/cancel  
4. **Lead qualification** — structured capture + lead records  
5. **Customer support FAQs** — knowledge-grounded answers  
6. **Call answering / overflow / after-hours coverage** — always-on agent answering  
7. **Inbound sales handling** — qualify, book next step, hand off  
8. **Human handoff** — warm/cold transfer with context  
9. **CRM writeback** — customers, leads, call records  
10. **Industry templates** — HVAC, plumbing, dental, legal, restaurants, call centers, etc. (configurable profiles; not hard-coded industry business logic inside the model core)

### Careful claims (do not overstate)

- Not a medical device; no clinical advice  
- Not a law firm; no legal advice  
- Not an insurance underwriter; escalate claims appropriately  
- Do not invent statistics, reviews, certifications (HIPAA/SOC2), or customer logos unless separately verified  
- Stripe metered overage invoicing and some enterprise items remain limited / sales-assisted

---

## 19. Deployment & operations

| Capability | Detail |
|---|---|
| Interactive installer | `deploy/install.sh` — domains, secrets, nginx, certs, compose |
| Host Postgres + Redis | Preferred production data plane (not in app containers) |
| Docker services | Platform, web, voice-agent (+ optional LiveKit) |
| Production hosts | `callandflow.com`, `api.callandflow.com`, optional `livekit.callandflow.com` |
| Health checks | Platform `/health`; compose healthchecks |
| Stripe webhook | `https://api.callandflow.com/billing/webhooks/stripe` |

See [`deploy/README.md`](./deploy/README.md) for firewall, Redis auth, and LiveKit TLS notes.

---

## 20. Security & safety (feature-relevant)

- Webhook signature verification  
- Session cookies + CORS allowlists  
- Internal token for service-to-service routes  
- Fail-closed tenant / profile resolve  
- Tool tenant isolation (no cross-tenant tool args)  
- Knowledge retrieval injection filtering  
- Rate limits on public token / sensitive endpoints (where implemented)  
- Robots disallow for ops paths  
- Redaction-minded logging practices in voice/platform services  

---

## 21. What is intentionally out of scope / not shipped as complete

Documented so sales and SEO do not over-promise:

| Topic | Status |
|---|---|
| Fake reviews / AggregateRating schema | Not used |
| Full Stripe metered overage invoicing | Not fully wired |
| Unlimited “any CRM” native connectors | Not a shipped universal integration hub |
| Collections / order support as first-class products | Roadmap themes in `TASKS.md`, not separate shipped modules |
| Self-serve custom domains | Not documented as complete |
| HIPAA / SOC 2 marketing claims | Only with real compliance evidence |

For planned expansions, see [`TASKS.md`](./TASKS.md) and [`web/SEO-ROADMAP.md`](./web/SEO-ROADMAP.md).

---

## 22. Quick capability checklist

Use this as a one-page “what can Call & Flow do?” list:

- [x] Multi-tenant workspaces  
- [x] AI voice agent (OpenAI Realtime + LiveKit)  
- [x] Multiple agent profiles + templates + marketplace install  
- [x] Call-flow configuration  
- [x] Browser marketing demo + tenant playground  
- [x] Connect / purchase phone numbers (Twilio + LiveKit SIP)  
- [x] Inbound SIP tenant resolve (fail-closed)  
- [x] CRM customers, leads, call records  
- [x] Appointment slots, book, reschedule, cancel  
- [x] Knowledge FAQs for voice answers  
- [x] Warm / cold human handoff  
- [x] Follow-up queue  
- [x] Jobs + dispatch board + tech mobile (plan-gated)  
- [x] Team roles + invites  
- [x] Stripe signup / checkout / portal / webhooks  
- [x] Usage + plan entitlements  
- [x] Automations (audit / follow-up job / webhook)  
- [x] Public API keys (`/v1` customers & calls)  
- [x] Tenant branding chrome  
- [x] Internal COGS views  
- [x] Marketing site + SEO foundations  
- [x] Self-host / Cloud deploy installer  

---

*Last updated: 2026-10-05 — sourced from `platform/`, `voice-agent/`, and `web/` implementations.*
