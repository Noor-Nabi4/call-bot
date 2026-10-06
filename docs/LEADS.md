# Leads (Phase 8)

First-class relational Lead CRM domain. Extends the existing `leads` table used by the voice agent; does **not** store core lead data in Dynamic CRM EAV.

## Model

| Field | Notes |
|-------|--------|
| `id`, `tenant_id` | Tenant-scoped PK |
| `customer_id` | **Nullable** FK → `customers` (SET NULL) |
| `title`, `description` | Lead subject (not customer PII) |
| `source` | Controlled enum (PHONE, WEBSITE, …, AI_AGENT, OTHER) |
| `priority` | LOW / MEDIUM / HIGH / URGENT |
| `status` | Pipeline status (see LEAD_PIPELINE.md) |
| `service_id`, `product_id` | Optional FKs to existing catalog |
| `owner_user_id` | Optional active `tenant_users` member |
| `prospect_*` | Non-authoritative contact when unconverted |
| `archived_at` | Soft archive |
| Voice legacy | `service_type`, `urgency`, `notes`, `call_id`, `idempotency_key`, `reference_code` |

Customer name/email/phone remain authoritative on Customer once linked.

## Unassociated / prospect Leads

A Lead may be created with `customer_id = NULL` (admin CRM or voice).

Voice/internal create (`LeadRepository` / `POST` internal `/leads`):

- `customer_id` is **optional**
- Cross-tenant `customer_id` fails closed
- Optional `prospect_name` / `prospect_phone` / `prospect_email`
- Do **not** fabricate a Customer merely to store a Lead

Conversion later links or creates the Customer explicitly.

## APIs

Admin base: `/api/admin/crm/leads`

- `GET/POST /leads`
- `GET/PATCH/DELETE /leads/{id}` (DELETE = archive)
- `POST /leads/{id}/restore`
- `POST /leads/{id}/transition` — **only** way to change status
- `POST /leads/{id}/convert`
- `GET /leads/{id}/activities`
- `GET/POST /leads/{id}/notes`, `PATCH/DELETE …/notes/{note_id}`
- `GET /leads/pipeline/counts` — server-side aggregation

Internal voice create remains on CRM routes via `LeadRepository` (optional customer).

## RBAC

`leads.read|create|update|delete|assign|transition|convert` and `leads.notes.*`.

AI Agent: read/create/update/transition + notes read/create. **Not** convert, delete, or assign.

Existing organizations pick up new system-role grants via `reconcile_system_roles_for_tenant` / `ensure_system_roles_for_tenant` (Phase 3.5 RBAC reconcile). No manual SQL.

## Tenant isolation

All queries filter `tenant_id` from the authenticated session (admin) or call-scope/internal auth (voice). Cross-tenant customer/service/product/owner refs fail closed.

## Archive

Default lists exclude `archived_at IS NOT NULL`. Archive preserves activities, notes, and conversion history.

Archived leads reject: update, transition, convert, note create. Restore first.

## Staging status

Local + PostgreSQL concurrency: VERIFIED (see hardening report). Staging/production: **NOT EXECUTED** → production readiness **BLOCKED**.
