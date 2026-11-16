# Lead Activities

Normalized `lead_activities` table (not a second customer timeline system).

## Fields

- `tenant_id`, `lead_id`
- `activity_type` (controlled)
- `actor_user_id`, `actor`
- `metadata` (JSON; no secrets)
- `created_at`

## Types

CREATED, STATUS_CHANGED, NOTE_*, OWNER_CHANGED, CUSTOMER_LINKED, SERVICE_LINKED, PRODUCT_LINKED, CONTACTED, BOOKED, WON, LOST, CONVERTED, UPDATED, ARCHIVED, RESTORED

## Idempotency

- Conversion retry (`already_converted: true`) does **not** emit another CONVERTED activity.
- Rejected transitions do **not** emit STATUS_CHANGED.

## Customer timeline

When a lead has `customer_id`, customer timeline (`type=LEAD`) includes:

1. Lead creation rows (`source=leads`)
2. Lead activity rows (`source=lead_activities`)

Requires `leads.read`. Does not invent orders/payments/invoices.
Unassociated leads do not appear on a customer timeline.
