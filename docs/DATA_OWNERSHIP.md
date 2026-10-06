# Data Ownership

**Date:** 2026-10-06  
**Goal:** Clear module ownership so domains can become separate databases later without rewriting the application.

Today this is a **modular monolith** on one Postgres database. Ownership is enforced by package boundaries and repository APIs — not by seven physical databases yet.

---

## Ownership map

```text
Identity   → owns identity / org membership data
CRM        → owns customer / lead / call identity data
Commerce   → owns product / order data          (not shipped)
Operations → owns jobs / appointments / dispatch
Billing    → owns SaaS subscription + future financial docs
AI         → owns agent config / conversation AI state
Analytics  → owns analytical aggregates         (not shipped)
Telephony  → owns DID provisioning / SIP routing
Knowledge  → owns curated KB articles
```

Canonical tenant root (`tenants`) is owned by **Identity / Organization**. Other domains reference `tenant_id` but do not own the tenant row.

Full table-by-table isolation status: `docs/TENANT_ISOLATION_AUDIT.md`.

---

## Identity

**Package:** `auth`, `organization`, `api_keys`, `branding`, `security`  
**Tables:** `tenants`, `tenant_users`, `tenant_api_keys`, `tenant_branding`, `organization_onboarding`, `organization_crm_*`

Owns:

- Organization profile (name, slug, status, timezone, geo/contact, industry, business model/size — see `docs/BUSINESS_CONFIGURATION.md`)
- User membership and roles
- Session/API-key authentication artifacts
- White-label branding
- Organization onboarding workflow state (`organization_onboarding` — see `docs/ONBOARDING_ARCHITECTURE.md`)
- Tenant CRM **configuration metadata** only (`organization_crm_configurations` + modules/statuses/fields/workflows — see `docs/CRM_CONFIGURATION.md`). Platform industry templates live in code, not in Identity tables.

Does **not** own: customers, calls, jobs, Stripe subscription lifecycle details beyond linking.

**External access:** other domains receive `tenant_id` + role/scopes from Identity; they must not invent membership.

---

## CRM

**Package:** `crm`  
**Tables:** `customers`, `customer_phones`, `leads`, `calls` (+ reads `call_cogs` via billing helper)

Owns:

- Customer identity and phones
- Leads and call session records
- Caller ↔ customer matching for voice tools

Does **not** own: appointments/jobs creation rules (Operations), SaaS invoices, agent prompt text, or organization CRM module/status/field **configuration** (Identity-owned metadata until Phase 3 domain packages claim it).

**Future (when required):** `customer_addresses`, `tags` / `customer_tags`, `customer_notes`, `customer_custom_fields` — still CRM-owned.

---

## Commerce

**Package:** none yet  
**Tables:** none

Planned ownership (do not create until product needs them):

```text
products, product_variants, product_prices, product_images,
categories, brands, product_categories,
inventory, inventory_locations, inventory_movements,
orders, order_items, order_status_history
```

Other domains must call Commerce APIs / tools (`search_products`, `check_inventory`, `create_order`) — never join Commerce tables from CRM/AI modules once separated.

---

## Operations

**Package:** `scheduling`, `jobs`, `queue`, `automation` (ops side)  
**Tables:** `tenant_schedule_settings`, `appointments`, `notification_outbox`, `technicians`, `jobs`, `job_notes`, `call_queue_items`, `automation_rules`

Owns:

- Availability and appointments
- Field jobs, assignments, notes
- Call queue / follow-up work items
- Automation rules that create operational side effects

May reference CRM ids (`customer_id`, `lead_id`, `call_id`) as **foreign keys today**; after DB split, store opaque external ids and resolve via CRM service.

---

## Billing

**Package:** `billing`  
**Tables:** `tenant_subscriptions`, `stripe_webhook_events`, `call_cogs`

Owns:

- SaaS plan entitlement and Stripe customer/subscription linkage
- Platform webhook idempotency ledger (`stripe_webhook_events` is global)
- Internal COGS estimates (`call_cogs`) — not customer invoices

**Future:** `invoices`, `invoice_items`, `payments`, `transactions` for end-customer billing — still Billing-owned; immutable financial history.

---

## AI

**Package:** voice-agent + platform `agent` profile surfaces; `handoff`  
**Tables:** `agent_profiles`, `tenant_agent_settings` (legacy), `tenant_handoff_settings`

Owns:

- Prompt/voice/tool configuration
- Handoff policy
- Per-call session state (in-memory / LiveKit room — not long-term DB unless persisted intentionally)

Does **not** own CRM/commerce rows. Voice uses an **AI tool gateway** into domain operations:

```text
Voice Agent → Tool Gateway → Domain repository/service
```

Analytics, embeddings, and summaries should be async consumers, not on the realtime audio path.

---

## Analytics

**Package:** none yet  
**Tables:** none in transactional DB for warehouse workloads

Owns (future):

- Aggregates, funnels, quality dashboards derived from events
- Separate analytics store fed by outbox / CDC

**Rule:** do not run heavy analytical queries against the transactional primary used by voice/CRM.

---

## Cross-cutting (temporary shared)

| Concern | Owner today | Notes |
|---------|-------------|-------|
| `telephony_*` audit/idempotency | Telephony | Keep with telephony DB if split |
| `tenant_retention_settings` | Admin / Identity | Policy only until recordings exist |
| Object storage metadata | Future Files domain | DB holds keys; blobs in S3/GCS |

---

## Boundary rules

1. **No domain should query another domain’s internal tables** once a service/DB split ships. Until then, prefer repository methods over cross-package SQLAlchemy joins in new code.
2. Sync coupling that exists today (scheduling auto-creates jobs; call end writes COGS) must become events or application services at the boundary when splitting.
3. Shared `tenant_id` is the only universal key; do not duplicate organization profile columns into every domain.
4. Voice tools map 1:1 to domain operations (`find_customer`, `create_appointment`, …) — never to raw multi-domain SQL.
