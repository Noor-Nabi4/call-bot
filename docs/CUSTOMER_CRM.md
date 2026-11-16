# Customer CRM

Phase 4 Customer CRM (Tasks 4.1–4.4) extends the existing first-class `customers` table.

> **Implementation-gate override:** This domain was implemented under an explicit local-development override. Staging and production readiness remain **BLOCKED** until the prerequisites in `docs/PRODUCTION_READINESS.md` are completed. Do not treat this work as deployable.

## Architecture

```text
Tenant
  └── Customers          (relational PLATFORM_ENTITY — not a Custom Object)
        ├── customer_phones
        ├── customer_locations
        ├── customer_tags / customer_tag_links
        ├── customer_notes   (historical notes)
        └── timeline         (aggregation over Calls/Leads/Jobs/Appointments/Notes/SMS/Email)
```

Dynamic CRM continues to treat `CUSTOMERS` as `PLATFORM_ENTITY` for custom fields and relationships.

## Data model

| Column | Notes |
|---|---|
| `name` | Canonical **display name** (voice-era callers depend on this) |
| `first_name` / `last_name` | Optional structured parts |
| `email` / `email_normalized` | Display + lowercase search value |
| `status` | `ACTIVE` \| `INACTIVE` (business state) |
| `archived_at` | Soft archive (lifecycle; separate from status) |
| `notes` | Short profile summary |
| `address` | Legacy flat address; synced from primary location when set |

Phones remain in `customer_phones` with `UNIQUE(tenant_id, e164)` via `normalize_e164`.

## Tenant isolation

- Tenant is always taken from authenticated `TenantContext` / session — never from request body authority.
- All queries filter `tenant_id` in SQL before returning rows.
- Cross-tenant IDOR attempts fail closed (`not_found`).

## RBAC

| Permission | Use |
|---|---|
| `customers.read` | List, get, search, timeline, tags list |
| `customers.create` | Create |
| `customers.update` | Update, restore, locations, tags, notes |
| `customers.delete` | Soft archive |

Timeline respects per-source permissions (`calls.read`, `leads.read`, `jobs.read`, `appointments.read`).

## Audit

Mutations use `write_audit` → `telephony_audit_events` (actions like `customer_created`, `customer_location_archived`, `customer_tag_added`).

## AI / voice

`CustomerService` exposes:

```text
find_customer / search_customers / get_customer
get_customer_locations / get_customer_timeline
create_customer / update_customer
```

Voice lookup/upsert remains on `CustomerRepository` + `/internal/crm/customers/*`.

## Migration

`0030_customer_crm` (after `0029_dynamic_crm_hardening`). Additive and backward compatible with voice-era rows.
