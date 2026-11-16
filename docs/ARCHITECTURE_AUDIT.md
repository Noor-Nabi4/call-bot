# Architecture Audit

**Date:** 2026-10-06  
**Scope:** Map the existing Call & Flow repo to [`ADVANCED_BUILD_TASKS.md`](../ADVANCED_BUILD_TASKS.md) (AI Business OS).  
**Prior roadmap:** [`TASKS.md`](../TASKS.md) is the completed **AI voice platform** plan (Phases 1–6 in that file). It is not the Business OS plan.

This audit describes **code that exists today**. Gaps are explicit. Do not invent a second tenant/org layer on top of `tenants`.

---

## 1. Repository layout

```text
call-bot/
├── web/            # Next.js  — marketing site + ops console
├── platform/       # FastAPI  — telephony, CRM, scheduling, jobs, billing, knowledge
├── voice-agent/    # LiveKit worker — OpenAI Realtime speech-to-speech
├── deploy/         # nginx, docker compose, installer
└── docs/           # this audit
```

| Layer | Stack | Entry |
|---|---|---|
| Frontend | Next.js (App Router), TypeScript | `web/` — marketing `:3002`, ops session cookie |
| Backend | FastAPI (`callbot_platform`) | `platform/src/callbot_platform/main.py` — `:8000` |
| Voice | LiveKit Agents + OpenAI Realtime | `voice-agent/src/agent.py` |
| Database | PostgreSQL (SQLAlchemy 2 + Alembic); tests often SQLite in-memory | `platform/src/callbot_platform/db/` |
| Cache | Redis (voice-agent profile cache when `REDIS_URL` set) | `docker-compose.yml` redis + agent |

Python package namespace remains `callbot_platform` for compatibility. Product brand is Call & Flow.

---

## 2. What already exists (inventory)

### 2.1 Authentication

- Public: `POST /auth/signup`, `/auth/login`, `/auth/logout`, `GET|PUT /auth/me`
- Internal bootstrap: `POST /auth/bootstrap` (`X-Internal-Token`)
- Ops session: HTTP-only JWT cookie (`SESSION_SECRET`, HS256)
- Voice/platform internal: `X-Internal-Token`
- Public API: hashed tenant API keys (`/v1/...`)
- Password hashing: bcrypt

Users are **not** a global identity table. `tenant_users` belong to one tenant (`tenant_id` + unique email per tenant). There is no multi-org membership.

### 2.2 Tenant / business model

Canonical tenant is `tenants` (`Tenant`):

| Field today | Notes |
|---|---|
| `id`, `name`, `slug`, `status` | `status`: `pending_subscription` / `active` / `suspended` |
| `timezone` | Also duplicated on schedule settings / agent profile hours |
| `industry_key` | Template key, nullable; API also exposes as `industry` |
| `business_type`, `currency`, `country`, `state` | Organization profile (`0019`) |
| `website`, `phone`, `email` | Organization profile |
| `default_agent_profile_id` | Phone routing fallback |
| `created_at`, `updated_at` | UTC timestamps |

**Missing vs Task 1.1 Organization:** none of the profile columns listed in Task 1.1 — implemented on `tenants` in migration `0019_tenant_organization_profile`.

**Do not create a parallel `organizations` table.** Extend `tenants` (or add a 1:1 `tenant_business_profiles` row) and treat `Tenant` as the organization.

### 2.3 Users and RBAC

`tenant_users.role` is a string. Valid roles in code:

- `admin`
- `dispatcher`
- `technician`

Enforcement: `require_ops_roles` / `require_entitled_ops_roles` on FastAPI; `useAuth({ roles })` on ops pages.

**Missing vs Task 1.3:** Owner, Manager, CSR, Accountant; permission matrix (today is role-string checks, not granular permissions).

### 2.4 Tenant isolation

- All CRM/jobs/calls/knowledge rows carry `tenant_id` with FKs and indexes.
- Voice tools reject client-supplied `tenant_id` override.
- Tenant resolve on inbound SIP is fail-closed.
- Env `TENANT_ID` fallback exists for single-business/dev (`ALLOW_ENV_TENANT_FALLBACK`).

Isolation is **application-level** (every query filters `tenant_id`), not Postgres RLS.

### 2.5 Calls

`calls`: room, customer, timestamps, `billable_seconds`, status, disconnect reason, metrics JSON, caller/called numbers, telephony provider IDs, QA (`disposition_code`, `quality_score`).

COGS: `call_cogs` per-call cost estimate (OpenAI tokens or per-minute fallback + LiveKit/Twilio rates).

### 2.6 Voice agent

- Shared LiveKit Cloud worker; tenant + Agent Profile resolved at dispatch.
- OpenAI Realtime (`OPENAI_API_KEY`, model/voice from profile).
- Prompts composed in versioned stacks (`prompts/`), gated tools via `enabled_tools`.
- Per-call `SessionUserData` / call facts; no invented long-term memory.
- Marketing demo is tenant-less (`source=marketing`); tenant testing is `/playground`.

Tools today:

| Group | Tools |
|---|---|
| CRM | `get_call_context`, `lookup_customer_by_phone`, `create_or_update_customer`, `create_lead` |
| Scheduling | `get_available_slots`, `book_appointment`, `reschedule_appointment`, `cancel_appointment` |
| Knowledge | `search_knowledge` |
| Handoff | `request_human_handoff` |
| SMS | Gated as a tool *group* on the profile; outbound SMS is booking notifications, not a general `send_sms` voice tool |

### 2.7 Twilio

- Path A: connect existing number / trunk
- Path B: platform purchase via Twilio
- Per-tenant Twilio subaccounts (`encrypted_auth_token`)
- DID uniqueness, LiveKit inbound trunk + dispatch rule IDs
- SMS for appointment confirm/reschedule/cancel when Twilio is configured
- Telephony audit + idempotency tables

### 2.8 LiveKit

- Rooms, SIP inbound trunks, dispatch rules, agent name `voice-agent`
- Warm/cold human transfer via tenant handoff settings (`sip_outbound_trunk_id`, escalation E.164)
- Web token mint for marketing demo (`web/src/app/api/token`)
- Cloud **or** self-hosted SFU via deploy installer

### 2.9 OpenAI

- Voice path: Realtime speech-to-speech (not STT→LLM→TTS as primary)
- Usage snapshot on call metrics for COGS
- Knowledge is **not** embeddings RAG; token overlap search on curated articles

### 2.10 Stripe

- **Platform SaaS billing only** (Checkout `price_data`, Customer Portal, signature-verified webhooks)
- Plans in code (`billing/plans.py`): Starter / Growth / Pro
- Entitlements: seats, numbers, knowledge docs (hard); voice minutes (soft / overage estimate)
- **Not** Stripe Connect. **Not** tenant merchant invoices, payment links, or customer charges for jobs

### 2.11 SMS

- Twilio SMS on appointment book/reschedule/cancel
- Outbox row `notification_outbox` (`channel=sms`, status + `provider_ref`)
- No inbound SMS webhook / SMS agent conversation loop

### 2.12 Email

- Appointment notifications write `notification_outbox` with `channel=email`
- Status typically `pending` — **no SMTP/SendGrid sender** in production path
- No template engine for estimates/invoices/receipts

### 2.13 CRM (today)

Tables: `customers`, `customer_phones` (unique `tenant_id`+E.164), `leads`, `calls`.

Customer fields: `name`, `email`, `address` (single string). No locations table, custom fields, custom objects, timeline entity, products, inventory, orders, estimates, invoices, memberships, equipment.

Leads: `service_type`, `urgency`, `status` (default `new`), `idempotency_key`, `reference_code`. No named pipeline stages as a first-class model.

### 2.14 Calendar / scheduling

- `tenant_schedule_settings`: timezone, slot minutes, horizon, weekly hours JSON
- `appointments`: book/reschedule/cancel, confirmation code, idempotency
- Availability engine is **business hours**, not per-technician calendars
- Booking auto-creates a `scheduled` job
- No Google/Outlook sync

### 2.15 Jobs / dispatch

- `jobs`, `job_notes`, `technicians` (optional GPS ping)
- Ops `/dispatch`, `/board`; tech mobile `/tech`
- Status transitions + checklist
- Technician availability as a schedule model: **missing** (techs exist; hours/status board is thin)

### 2.16 Knowledge

- Curated `knowledge_articles` (tenant + optional `agent_profile_id`)
- Injection-filtered retrieval
- Plan document caps
- No document ingestion pipeline, chunking, or vector store

### 2.17 Background jobs / queues / events

| Mechanism | Role |
|---|---|
| `notification_outbox` | SMS send + email pending rows (inline on booking, not a worker) |
| `automation_rules` | In-process: `call.ended`, `call.handoff_requested`, `appointment.created` → audit / follow-up job / signed webhook |
| `call_queue_items` | Ops follow-up queue (claim/complete) |
| Redis | Agent profile cache only |
| **Celery / RQ / SQS** | **None** |

There is no durable event bus. Automations run in the request/call-end path.

### 2.18 Integrations

- Twilio, LiveKit, OpenAI, Stripe (SaaS)
- Outbound HTTPS webhooks (`post_webhook` + HMAC, SSRF guards)
- Marketplace: **in-product agent templates**, not third-party OAuth apps
- **Missing:** HubSpot, Salesforce, ServiceTitan, Google Calendar, Outlook, Shopify, WooCommerce, QuickBooks, Xero

### 2.19 Frontend (ops)

Shipped: dashboard, dispatch, customers, live, supervisor, queue, calls, appointments, metrics, playground, agents + flow builder, marketplace, phones, knowledge, handoff, settings (team, billing, COGS, automations, API keys, branding), tech mobile.

**Missing vs Business OS UI:** products, inventory, services/pricebook, orders, estimates, invoices, memberships, equipment, calendar day/week drag-drop, revenue/outstanding invoices KPIs.

### 2.20 Onboarding

`/signup` is multi-step → Stripe Checkout. Industry templates can be applied later via agents/marketplace.

**Missing vs Phase 2:** onboarding state machine, business-model module picker, automatic CRM module provisioning, AI NL business-setup assistant.

---

## 3. Data model (current)

```text
Tenant 1──* TenantUser (role: admin|dispatcher|technician)
      1──* AgentProfile ──* TenantPhoneNumber
      1──1 TenantAgentSettings (legacy; profiles are source of truth)
      1──1 TenantScheduleSettings
      1──1 TenantHandoffSettings
      1──1 TenantRetentionSettings
      1──1 TenantSubscription
      1──1 TenantBranding
      1──1 TenantTwilioSubaccount?
      1──* Customer ──* CustomerPhone
      1──* Lead
      1──* Call
      1──* Appointment ──* NotificationOutbox
      1──* Job ──* JobNote
      1──* Technician
      1──* KnowledgeArticle
      1──* AutomationRule
      1──* CallQueueItem
      1──* TenantApiKey
```

Alembic: `0001`–`0018` (telephony through call COGS).

---

## 4. TASKS.md vs ADVANCED_BUILD_TASKS.md

| [`TASKS.md`](../TASKS.md) (voice platform) | Status | [`ADVANCED_BUILD_TASKS.md`](../ADVANCED_BUILD_TASKS.md) (Business OS) |
|---|---|---|
| Multi-tenant voice, profiles, telephony | Done in code | Phase 1: extend org fields + RBAC |
| CRM lookup/upsert, leads, calls | Thin CRM | Phases 3–9: modules, custom fields/objects, products, inventory, orders |
| Scheduling + jobs + dispatch | Field-service MVP | Phases 10–12: richer job/tech availability |
| Knowledge keyword search | Done | Phase 16: RAG / embeddings |
| Stripe SaaS + usage | Done (no Connect) | Phases 17–19: estimates, invoices, tenant payments |
| Automations (3 triggers) | Thin | Phase 22: event bus + workflow builder |
| Call QA scores | Thin | Phase 23: recording, transcript, AI summary, classification |
| Warm/cold handoff | Done | Phase 24: department/tech/hours routing |
| Public `/v1` customers+calls | Thin | Phase 28: CRM/calendar/commerce/accounting OAuth |
| — | — | Phases 5–7, 15, 20–21, 29: catalog, SMS agent, memberships, assets, AI setup |

**Principle:** Keep the voice platform as the AI layer. Grow CRM/commerce **inside** `platform/` with the same `tenant_id` isolation. Do not fork a second app.

---

## 5. Gap map by advanced phase

Legend: **exists** / **partial** / **missing**

| Phase | Title | Status | Reuse |
|---|---|---|---|
| 0 | Architecture audit | **this document** | — |
| 1 | Multi-tenant foundation | **partial** | Org profile on `tenants` (1.1 done). Membership (1.2) and richer RBAC (1.3) still open. |
| 2 | Business onboarding | **partial** | `/signup` + `industry_key` + templates; add wizard state |
| 3 | Dynamic CRM engine | **missing** | New tables; do not overload `customers` JSON without a schema |
| 4 | Customer CRM | **partial** | Extend `customers`; add locations + search + timeline |
| 5 | Product catalog | **missing** | New |
| 6 | Inventory | **missing** | New |
| 7 | Services & pricebook | **missing** | Today `service_type` is a free-text string on leads/jobs/appts |
| 8 | Leads | **partial** | Extend `leads` + pipeline |
| 9 | Orders | **missing** | New |
| 10 | Jobs | **partial** | Extend `jobs` status machine |
| 11 | Appointments | **partial** | Per-tech availability is the main gap |
| 12 | Dispatch | **partial** | Board exists; tech status/ETA thin |
| 13 | AI tool layer | **partial** | Formalize registry; add commerce/job/billing tools only after domain tables exist |
| 14 | AI voice agent | **partial** | Identity/booking/prompts exist; commerce tools blocked on catalog |
| 15 | AI SMS agent | **missing** | Inbound webhook + conversation store |
| 16 | Knowledge / RAG | **partial** | Articles + search; no embeddings |
| 17 | Estimates | **missing** | New |
| 18 | Invoicing | **missing** | New |
| 19 | Payments | **partial** | SaaS Stripe only; tenant payment links missing |
| 20 | Memberships | **missing** | New |
| 21 | Equipment | **missing** | New |
| 22 | Automation engine | **partial** | Rules table; no visual builder / generic event log |
| 23 | Call intelligence | **partial** | QA score; no recording/transcript/summary pipeline |
| 24 | Human handoff | **partial** | Warm/cold + queue; no department/hours routing matrix |
| 25 | Communication automation | **partial** | One appointment SMS/email body; no templates |
| 26 | Admin dashboard | **partial** | Ops shell; missing commerce screens |
| 27 | Analytics | **partial** | `/metrics` voice-centric; no revenue/ops utilization |
| 28 | Integrations | **partial** | Webhook action only |
| 29 | AI business setup | **missing** | After modules exist |
| 30 | AI agent configuration | **partial** | Agent Profile + flow builder already cover most of this |
| 31 | AI guardrails | **partial** | Safety prompts + restricted topics; expand tests |
| 32 | AI cost tracking | **partial** | Internal COGS exists; tenant-facing AI cost is not a product |
| 33 | Security | **partial** | Sessions, HMAC webhooks, encryption of Twilio tokens, rate limits |
| 34 | Observability | **partial** | Structured logs + call metrics |
| 35–36 | AI testing / golden flows | **partial** | Unit/API tests; limited LiveKit agent eval suite |
| 37 | Production readiness | **partial** | Deploy installer, CI, compose; continue hardening |

---

## 6. Recommended implementation order (do not skip domain before AI tools)

1. **Phase 1 (extend, don’t replace):** org profile fields on `tenants`; optional richer RBAC; keep `tenant_id` as the isolation key everywhere.
2. **Phase 2:** onboarding state + business-model flags that **enable modules** (feature flags on tenant), using existing industry templates.
3. **Phase 7 then 4/8/10/11:** services/pricebook so `service_type` stops being free text; then customer locations/search; lead pipeline; job/appointment technician availability.
4. **Phases 5–6, 9, 17–21:** commerce only if the tenant’s business model enables those modules.
5. **Phase 13 tools:** add tools **after** the tables exist. No mock catalog in the voice path.
6. **Phase 16 RAG / 15 SMS / 23 transcripts:** after CRM writes are stable, so retrieval is not the only memory.
7. **Phase 19 tenant payments:** separate Stripe Connect (or equivalent) from existing SaaS Stripe keys.

### Hard constraints from this codebase

- Never put fake customers, slots, products, or tool results in `platform/` or `voice-agent/` application code.
- Voice tools must stay tenant-scoped from session resolve, not request body `tenant_id`.
- Do not block the realtime audio path on heavy CRM/analytics work; persist async after the turn.
- SaaS `STRIPE_SECRET_KEY` must not be reused for tenant merchant charges.

---

## 7. External setup (already required; unchanged by this audit)

- Postgres (`DATABASE_URL`) + Alembic in production
- LiveKit Cloud (`LIVEKIT_URL`, API key/secret) and optional SIP host
- OpenAI (`OPENAI_API_KEY` on the worker)
- Twilio (account or per-tenant subaccount) for DID + SMS
- Stripe platform account + webhook to `/billing/webhooks/stripe`
- `SESSION_SECRET`, `INTERNAL_SERVICE_TOKEN`, `CREDENTIALS_ENCRYPTION_KEY`, `METADATA_HMAC_SECRET`
- Optional Redis for shared agent-profile cache

---

## 8. Risks if Phase 1 is implemented naively

- Renaming `Tenant` → `Organization` would break every FK, session JWT (`tenant_id`), voice resolve, and ops UI.
- Adding a second org table would split isolation and invite IDOR bugs.
- Expanding RBAC without migrating existing `admin`/`dispatcher`/`technician` rows would lock operators out.
- Turning knowledge into RAG without injection filtering would regress current safety behavior.
