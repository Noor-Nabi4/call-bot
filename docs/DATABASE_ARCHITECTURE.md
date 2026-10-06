# Database Architecture

**Date:** 2026-10-06  
**Scope:** Call & Flow platform (`platform/`) — audit of what exists, proposed target, and incremental changes.  
**Principle:** One table = one clear business responsibility. Do not create commerce/order tables until those products ship.

---

## 1. Existing architecture

### Stack

| Layer | Technology |
|-------|------------|
| Database | PostgreSQL (`postgresql+psycopg`) |
| ORM | SQLAlchemy 2.x (`Mapped` / `mapped_column`) |
| Migrations | Alembic (`platform/src/alembic/versions/`, 0019 head before scaling work) |
| Sessions | Sync `Session` via `get_db()` — commit on success, rollback on error |
| Tests | Often SQLite in-memory via same models (`JsonType` → JSON) |

### Tenancy model

- Root entity: `tenants` (organization). There is **no** separate `organizations` table.
- Tenant-owned rows carry `tenant_id` (UUID FK → `tenants.id`, usually `ON DELETE CASCADE`).
- Isolation is **application-enforced** (repo filters), not Postgres RLS.
- Canonical identifier in code/APIs: `tenant_id` (equivalent to `organization_id` in the design brief).

### Current tables by responsibility (28)

| Domain | Tables |
|--------|--------|
| Identity / org | `tenants`, `tenant_users`, `tenant_api_keys`, `tenant_branding` |
| Telephony | `tenant_phone_numbers`, `tenant_twilio_subaccounts`, `telephony_audit_events`, `telephony_idempotency_keys` |
| AI config | `agent_profiles`, `tenant_agent_settings` (legacy), `tenant_handoff_settings` |
| CRM | `customers`, `customer_phones`, `leads`, `calls` |
| Scheduling | `tenant_schedule_settings`, `appointments`, `notification_outbox` |
| Operations | `technicians`, `jobs`, `job_notes`, `call_queue_items` |
| Knowledge | `knowledge_articles` |
| Billing (SaaS) | `tenant_subscriptions`, `stripe_webhook_events` |
| Cost / retention | `call_cogs`, `tenant_retention_settings` |
| Automation | `automation_rules` |

### What does **not** exist yet

Commerce catalog, variants, inventory, customer invoices/payments, order line items, analytics warehouse, object-storage file metadata, generic domain-event outbox, Postgres RLS, dedicated-DB-per-tenant.

---

## 2. Audit findings (do not blindly rewrite)

### Strengths

- Most business tables are already tenant-scoped with FKs and many composite unique constraints (`(tenant_id, e164)`, `(tenant_id, slug)`, etc.).
- CRM customers are lean; phones are correctly split into `customer_phones`.
- Jobs notes are separate (`job_notes`) — notes do not bloat the job row.
- Idempotency keys exist for leads, appointments, telephony mutations.
- `call_cogs` separates cost accounting from the call lifecycle row.
- `notification_outbox` is a real outbox table (worker drain still incomplete for email).

### Problems

| Issue | Impact |
|-------|--------|
| Legacy `/tenants/{tenant_id}/…` telephony routes were unauthenticated | Cross-tenant telephony mutation risk |
| Shared `INTERNAL_SERVICE_TOKEN` + caller-chosen `tenant_id` on internal APIs | Token leak = full data plane |
| Default SQLAlchemy pool (no `pool_size` / `pool_pre_ping`) | Exhaustion under multi-worker load |
| Missing `(tenant_id, status[, created_at])` indexes on `calls`, `leads`, outbox, audit | Slow ops list/filter queries |
| Model ↔ migration index drift (`ix_calls_tenant_ended_at`) | Recreate from models misses indexes |
| `tenant_agent_settings` duplicates `agent_profiles` | Dual source of truth |
| `calls` mixes lifecycle + QA + metrics | Wide hot table; acceptable short-term |
| External I/O inside request DB transactions (Twilio, SMS, webhooks) | Long locks, partial failures |
| Unbounded knowledge `list()` | Memory risk as KB grows |
| No `TenantDatabaseStrategy` | Cannot add dedicated DB without app-wide rewrites |

### JSON fields — keep vs split later

**Keep as JSON (config/audit bags):** `calls.metrics`, telephony audit/idempotency payloads, `provisioning_details`, COGS snapshots, weekly hours, prompt fact bags, automation `config`.

**Candidates to relationalize when product needs queryability:** `knowledge_articles.tags`, `jobs.checklist`, `agent_profiles.enabled_tools` / `call_flow`, API key scopes.

### Tables that should stay relatively denormalized

- `agent_profiles` — hot path for voice; cacheable; splitting increases joins on every call.
- `calls` core identity columns — keep until volume forces `call_quality` / `call_metrics` split.
- `customers` core fields — single address Text is fine until multi-address is a product requirement.

---

## 3. Proposed architecture (target)

### Near-term (implemented / in progress)

1. Central **tenant resolution + DB strategy** module (`callbot_platform.tenancy`).
2. Tunable **connection pooling**.
3. Query-pattern **indexes** for high-volume list filters.
4. Auth gate on legacy telephony path routes.
5. Bounded list APIs / shared pagination helpers.
6. Documented domain ownership so modules can split DBs later.

### Medium-term (when product requires)

| Change | Trigger |
|--------|---------|
| Split `call_quality` from `calls` | Heavy QA reporting / wide row pain |
| Deprecate `tenant_agent_settings` | All readers on `agent_profiles` |
| `customer_addresses`, tags M2M, custom fields EAV | CRM Task requirements |
| `job_checklist_items`, `job_status_history` | Field ops auditability |
| Commerce tables (`products`, variants, prices, inventory, orders) | Commerce MVP |
| Customer invoices/payments | Billing beyond SaaS Stripe |
| `files` metadata + object storage | Recordings / KB uploads |
| `domain_events` outbox + workers | Async email, analytics, AI summaries |
| Postgres RLS as defense in depth | Enterprise compliance |
| Partition `calls` / audit by time | Sustained multi-tenant call volume |

### Table responsibility map (current + planned)

```text
tenants                    → organization identity + profile
tenant_users               → identity membership + role
customers                  → CRM party identity
customer_phones            → CRM phone identities (tenant-unique E.164)
leads                      → inbound opportunity
calls                      → voice session lifecycle
call_cogs                  → per-call cost estimate
appointments               → scheduled visit
jobs                       → field work order
job_notes                  → work-order commentary
agent_profiles             → voice agent configuration
knowledge_articles         → curated KB content
tenant_subscriptions       → SaaS plan entitlement
notification_outbox        → durable notification intents
```

---

## 4. Relationships (core)

```text
tenants 1──* customers 1──* customer_phones
tenants 1──* calls *──? customers
tenants 1──* leads *──1 customers
tenants 1──* appointments *──1 customers
tenants 1──* jobs *──1 customers
jobs *──? appointments / leads / calls / technicians
calls 1──0..1 call_cogs
tenants 1──* agent_profiles
tenant_phone_numbers *──? agent_profiles
```

Cross-domain links today use FKs across packages (scheduling → jobs, CRM → COGS). Future separation should replace direct FK reads with **domain APIs / events**, keeping FKs only inside a domain’s database.

---

## 5. Index strategy

### Keep / verify

- All `tenant_id` filters
- Tenant-aware uniques (`customer_phones`, leads/appointments idempotency, agent profile slugs)
- `appointments (tenant_id, starts_at)`
- `jobs (tenant_id, status)`
- `call_queue_items (tenant_id, status, created_at)`
- `call_cogs (tenant_id, created_at)`
- `calls (tenant_id, ended_at)` (usage)

### Added for list/filter hot paths

- `calls (tenant_id, status, started_at)`
- `leads (tenant_id, status, created_at)`
- `appointments (tenant_id, status)`
- `notification_outbox (tenant_id, status, created_at)`
- `telephony_audit_events (tenant_id, created_at)`
- `jobs (tenant_id, created_at)`

Do **not** index every column; add only from observed admin/API query patterns.

---

## 6. Tenant strategy

See [TENANCY_ARCHITECTURE.md](./TENANCY_ARCHITECTURE.md).

Summary: shared database today; `TenantDatabaseStrategy` resolves `shared` vs `dedicated` so enterprise tenants can move without rewriting repositories.

---

## 7. Caching strategy

| Data | Cache | Key shape | TTL / invalidation |
|------|-------|-----------|--------------------|
| Agent profile | Redis (voice-agent) | `callbot:va:agent_profile:{tenant_id}[:{profile_id}]:…` | Versioned; reject mismatched `tenant_id` |
| Settings | Process `lru_cache` | N/A (config) | Process lifetime |
| Rate limits | In-process today | Actor / API key | Move to Redis for multi-instance |
| Customers / products | Not cached yet | `tenant:{id}:customer:{id}` when added | Short TTL + write invalidation |

**Rule:** every cache key that holds tenant data must include `tenant_id`. Never serve Tenant A’s payload to Tenant B.

---

## 8. Scaling strategy

See [DATABASE_SCALING.md](./DATABASE_SCALING.md).

Order of operations: fix isolation → pool + indexes → async outbox → archive/partition high-volume tables → dedicated DB for large tenants → analytics DB.

---

## 9. Implementation rules for this codebase

1. Prefer migrations over ad-hoc DDL.
2. Preserve existing API shapes unless security requires a break.
3. Do not invent commerce/order schemas ahead of product.
4. Repositories always take authenticated `tenant_id`; never trust body/path tenant alone for ops.
5. Keep voice path free of heavy analytics joins.
6. Short DB transactions; external I/O after commit via outbox where possible.
