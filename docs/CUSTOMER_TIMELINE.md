# Customer Timeline

Timeline is an **aggregation layer** over authoritative domain tables. It does not duplicate Call/Lead/Job/Appointment rows into a `customer_timeline` table.

> Implemented under the Phase 4 **implementation-gate override**. Staging-scale validation is **NOT EXECUTED**. No fake commerce domains are invented.

## Endpoint

```http
GET /api/admin/crm/customers/{customer_id}/timeline
```

Query params: `event_type`, `limit` (≤100), `cursor`, `since`, `until`.

## Included sources (when present)

| Type | Source table | Timestamp | Permission |
|---|---|---|---|
| `CALL` | `calls` | `started_at` | `calls.read` |
| `LEAD` | `leads` | `created_at` | `leads.read` |
| `JOB` | `jobs` | `created_at` | `jobs.read` |
| `APPOINTMENT` | `appointments` | `starts_at` | `appointments.read` |
| `NOTE` | `customer_notes` | `created_at` | `customers.read` |
| `SMS` / `EMAIL` | `notification_outbox` via customer appointments | `created_at` | `appointments.read` |

Orders / invoices / payments / estimates are **omitted** until those domains exist.

## Ordering

1. `occurred_at DESC`  
2. Stable `source_key` (`call:{id}`, `lead:{id}`, …)

## Pagination

Each source query is bounded (`limit + 1`). Results are merged, sorted, then keyset-filtered. This avoids loading entire histories into memory.

## Authorization

Timeline is not a permission bypass. Missing source permissions simply omit that event type.
