# Tenant Isolation Audit (Task 1.4)

**Date:** 2026-10-06  
**Canonical boundary:** authenticated principal → `TenantContext` → repository/service → `WHERE tenant_id = :tenant_id`  
**Authoritative tenant:** server-derived session / API key / call-scope / job payload — never client body/query alone.

See also: `docs/TENANCY_ARCHITECTURE.md`, `docs/DATA_OWNERSHIP.md`.

---

## Tenant boundary

```text
Authenticated Principal
        ↓
TenantContext(tenant_id, source)
        ↓
Repository / Service (tenant_id required)
        ↓
Tenant-scoped query
        ↓
Resource
```

Canonical implementation: `callbot_platform.tenancy.context` (`TenantContext`, `require_tenant_context`, `set_tenant_context`).

Missing context: **fail closed** via `require_tenant_context()` → `RuntimeError`. Do not default to first/public/NULL/admin tenant.

---

## Ownership matrix

| Domain | Table/Resource | Tenant owned? | Tenant enforcement | Status |
|--------|----------------|--------------:|--------------------|--------|
| Identity | `tenants` | Root | PK = tenant; ops use `user.tenant_id` | PASS |
| Identity | `tenant_users` | Yes | `tenant_id` | PASS |
| Identity | `tenant_api_keys` | Yes | `tenant_id` + revoke by `(tenant_id, id)` | PASS |
| Identity | `tenant_branding` | Yes | `tenant_id` | PASS |
| Identity | `organization_onboarding` | Yes | `UNIQUE(tenant_id)` + session scope | PASS |
| Identity | `tenants.business_size` | Yes | session-scoped org update | PASS |
| CRM config | `organization_crm_*` | Yes | `tenant_id` + unique keys | PASS |
| Platform | industry CRM templates | No (code registry) | immutable; tenant copies only | PASS (global) |
| RBAC | `permissions` | No (platform) | Global catalog | PASS (global) |
| RBAC | `organization_roles` | Yes | `tenant_id` | PASS |
| RBAC | `role_permissions` | Hybrid | Via role → tenant | PASS |
| RBAC | `role_permission_tombstones` | Hybrid | Via role → tenant | PASS |
| RBAC | `member_roles` | Hybrid | Via `tenant_users` | PASS |
| CRM | `customers` | Yes | `tenant_id` on get/upsert/phone | PASS |
| CRM | `customer_phones` | Yes | `UNIQUE (tenant_id, e164)` | PASS |
| CRM | `leads` | Yes | `tenant_id` | PASS |
| CRM | `calls` | Yes | `tenant_id` + call-scope check | PASS |
| CRM | `tenant_agent_settings` | Yes | `tenant_id` | PASS |
| AI | `agent_profiles` | Yes | `tenant_id` | PASS |
| AI | `tenant_handoff_settings` | Yes | `tenant_id` | PASS |
| AI | `tenant_retention_settings` | Yes | `tenant_id` | PASS |
| Knowledge | `knowledge_articles` | Yes | `tenant_id` on list/search/CRUD | PASS |
| Operations | `appointments` | Yes | `tenant_id` | PASS |
| Operations | `tenant_schedule_settings` | Yes | `tenant_id` | PASS |
| Operations | `notification_outbox` | Yes | `tenant_id` + worker `TenantContext` | PASS |
| Operations | `technicians` | Yes | `tenant_id` | PASS |
| Operations | `jobs` | Yes | `tenant_id` on get/list/assign | PASS |
| Operations | `job_notes` | Yes | `tenant_id` | PASS |
| Operations | `call_queue_items` | Yes | `tenant_id` + call join scoped | PASS |
| Operations | `automation_rules` | Yes | `tenant_id` | PASS |
| Telephony | `tenant_phone_numbers` | Yes | `_owned` / `(id, tenant_id)` | PASS |
| Telephony | `tenant_twilio_subaccounts` | Yes | `tenant_id` | PASS |
| Telephony | `telephony_audit_events` | Yes* | ops list by `tenant_id`; nullable for platform-only | PASS |
| Telephony | `telephony_idempotency_keys` | Yes | `UNIQUE (tenant_id, operation, key)` | PASS |
| Billing (SaaS) | `tenant_subscriptions` | Yes | `tenant_id`; Stripe via customer/ref map | PASS |
| Billing (SaaS) | `stripe_webhook_events` | No (global ledger) | Idempotency only | PASS (global) |
| Billing | `call_cogs` | Yes | `tenant_id` | PASS |
| Files | `recording_objects` | Yes | `tenant_id` + key `tenant/{id}/…` + presign after ownership | PASS |
| Jobs | `async_jobs` | Yes | `tenant_id`; get with tenant filter | PASS |
| Commerce | products / inventory | N/A | Not shipped | N/A |
| Billing (customer) | invoices / payments | N/A | Not shipped (SaaS Stripe only) | N/A |

\* `telephony_audit_events.tenant_id` may be NULL for intentional platform-level events; tenant ops queries always filter `tenant_id = authenticated`.

---

## Repository / API enforcement

- Domain repositories take `tenant_id` as the first argument and filter in SQL.
- Ops routes use `CurrentUser.tenant_id` from session JWT (re-checked in DB).
- Public `/v1` uses API-key → `TenantApiKey.tenant_id`.
- Internal voice CRM uses `X-Call-Scope` (`require_call_scope` / `optional_or_required_call_scope`) and must not weaken shared-token god-mode without call binding.
- Legacy `/tenants/{tenant_id}/…` telephony routes require `X-Internal-Token`.

---

## AI / RAG

- Knowledge search: `WHERE tenant_id = :tenant_id` before scoring (no post-filter-only global scan).
- Voice tools derive tenant from session userdata / call resolve; LLM-supplied `tenant_id` is rejected (`voice-agent` scheduling tools).
- AI tool permissions: `require_ai_tool_permission(session, tenant_id, …)` after tenant is known.

---

## File / object storage

- Keys prefixed `tenant/{tenant_id}/…` via `ObjectStorage._key` / filesystem path.
- `RecordingStorageService.get_recording` / `presign_download` require `(tenant_id, recording_id)` before issuing URLs.
- Never generate a signed URL from a raw object key alone.

---

## Cache

- Helper: `tenant_cache_key(tenant_id, *parts)` → `tenant:{uuid}:…`
- Voice agent profile cache keys include tenant (and profile) identity; mismatched `tenant_id` in payload is rejected.

---

## Background jobs / outbox / webhooks

- `async_jobs.tenant_id` required; workers set `TenantContext(..., source=JOB)`.
- Outbox workers set job tenant context before SMS/send.
- Stripe webhooks: verify signature → resolve subscription/customer → existing `tenant_subscriptions` row (never trust alone an internal id from payload without mapping).
- Telephony provision handlers verify `phone.tenant_id == job.tenant_id`.

---

## Admin / support

- Organization **Admin** is tenant-scoped via membership + RBAC.
- Platform god-mode = shared `INTERNAL_SERVICE_TOKEN` (documented risk; call-scope hardens CRM). Not granted to org users.

---

## Cross-tenant test coverage

Primary suite: `platform/tests/test_tenant_isolation.py`  
Also: outbox isolation in `test_phase2_scaling.py`, call-scope in `test_phase3_1_hardening.py`, RBAC in `test_rbac.py`.

Covers: customers, leads, appointments, jobs, calls, knowledge, audit, recordings/presign, branding, API keys, async jobs, require_tenant_context fail-closed, telephony route auth.

---

## Known exceptions / N/A

| Item | Notes |
|------|-------|
| Products / invoices / payments (customer billing) | Not in schema — Phase 4 gated |
| Postgres RLS | Not enabled; app-layer filters are primary (see TENANCY_ARCHITECTURE) |
| Shared internal token | Path `tenant_id` trusted when token present on legacy telephony / some pre-call routes; CRM mitigated by call-scope. **Follow-up:** Task 1.4.1 — Internal Service Tenant Boundary Hardening |
| `stripe_webhook_events` | Global by design |
| `permissions` | Global catalog |

---

## Migration

**Not required** for Task 1.4: tenant-owned tables already carry `tenant_id` through `0025_rbac_reconciliation`. No ambiguous orphan rows identified that need unsafe backfill.

---

## Hardening applied in 1.4

- Phone refresh after provision/release: load by `(id, tenant_id)` (routes + agent admin).
- Technician create: load profile by `(id, tenant_id)`.
- Recording metadata + presign: tenant-scoped APIs.
- Queue claim/complete: call join filtered by `tenant_id`.
- Telephony `_owned` helpers: atomic `(id, tenant_id)` select.
- Async job get: filter by `tenant_id` in SQL when provided.
