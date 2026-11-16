# Memberships (Phase 20)

Tenant-scoped membership plans and customer subscriptions.

**Status:** Application implementation complete; Stripe/provider/staging verification pending.  
**Production gate:** `PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN`

## Billing architecture (Option A)

Phase 19 provides Checkout Sessions (`mode=payment`), not Stripe Subscriptions.

```text
Membership plan / interval
  ↓
CustomerMembership (PENDING)
  ↓
Invoice (CUSTOM line — server price)
  ↓
PaymentService.create_payment_link (optional)
  ↓
Verified payment → InvoicePaymentService
  ↓
MembershipService.on_invoice_paid → ACTIVE / renew period
```

Do **not** introduce a second payment ledger. Stripe Subscriptions are out of scope until explicitly required.

## Application vs provider vs invoice state

| Layer | Role |
| ----- | ---- |
| `customer_memberships.status` | Entitlement / lifecycle (PENDING, ACTIVE, …) |
| Invoice / Payment | Money collection (Phase 18/19) |
| Stripe Checkout | Card collection only |

Browser success redirects are not authoritative.

## Plan pricing

- `monthly_price` and `annual_price` are independent (not auto `× 12`).
- Currency follows invoice conventions (`USD` default, `Numeric(19,4)`).
- Only `ACTIVE` plans can be subscribed.

## Customer membership rules

- **One open membership per customer** (`PENDING` / `ACTIVE` / `PAST_DUE` / `PAUSED`) — DB partial unique index + app check.
- Subscribe → `PENDING` until first period invoice is **PAID**.
- **Cancel default:** `cancel_at_period_end` (entitlements until period end). Immediate cancel supported explicitly; **no automatic refund**.
- **Upgrade / downgrade:** scheduled via `pending_plan_id`, effective at **next billing period**. **No proration.**

## Refund / cancel money policy

Membership cancellation does not invent refunds. Use Phase 19 payment refunds on the related invoice payment when a financial reversal is required.

## Entitlements

`MembershipEntitlementService` is the single resolver for:

- active membership
- service discount (PERCENTAGE / FIXED_AMOUNT; never negative totals)
- included-service remaining quantity (per period)
- priority scheduling flag

Consumers: PricingService (optional `customer_id`), AppointmentService (priority bump NORMAL→HIGH; entitlement consume on book). Priority never bypasses availability or double-booking rules.

## AI tools

| Tool | Confirmation |
| ---- | ------------ |
| `list_membership_plans` | read-only |
| `get_customer_membership` | read-only |
| `subscribe_membership` | required |
| `cancel_membership` | required |
| `upgrade_membership` | required |
| `downgrade_membership` | required |

RAG must not answer current membership status. Mutations use Phase 14 confirmation + `operation_id`.

## Migration

`0048_memberships` — `membership_plans`, `membership_plan_services`, `customer_memberships`, `membership_history`, `membership_billing_periods`, `membership_entitlement_usage`

## Verification

| Check | Status |
| ----- | ------ |
| Local membership unit tests | VERIFIED (`test_memberships_crm.py` — 5 passed) |
| Full platform pytest | VERIFIED (620 passed, 1 skipped; Phase 19 flake still documented separately) |
| Stripe test-mode membership billing | NOT EXECUTED |
| Staging | NOT EXECUTED |
| Performance / EXPLAIN | NOT EXECUTED |
