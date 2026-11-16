# Lead Conversion

**WON does not automatically convert a Lead.**

Conversion is explicit via `POST /leads/{id}/convert` (admin) and requires `leads.convert`.

## Behavior

1. Lock lead (`FOR UPDATE`)
2. If `lead_conversions` row exists → return `already_converted: true` (HTTP 200) with **no** new activity/audit
3. Resolve customer:
   - `customer_id` (same tenant), or
   - `create_customer` / prospect fields with phone then email match via Customer CRM, or
   - existing `lead.customer_id`
4. Insert `lead_conversions` with `UNIQUE(tenant_id, lead_id)`
5. Set `converted_at`, `converted_by`, `converted_customer_id`, link `customer_id`
6. Activities CONVERTED + CUSTOMER_LINKED; audit `lead_converted` (only on first success)

## Matching

Prefer existing Customer by **phone** (E.164) then **email** (normalized). Do not match on name alone.

## Idempotency / concurrency

PostgreSQL uniqueness + row lock ensure exactly one conversion. Concurrent second request returns the existing conversion. Retries must not create duplicate Customers, conversions, or CONVERTED activities.

Do **not** use Redis for correctness.

## Out of scope

Jobs, estimates, invoices, appointments from conversion.
