# Estimates (Phase 13)

Commercial quotes connecting `Customer → Estimate → Approval → Job / Order`. Invoices and payments are **not** implemented in this phase.

## Authoritative services

| Concern | Service |
|---------|---------|
| Estimate CRUD / items / totals | `EstimateService` |
| Status transitions | `EstimateTransitionService` |
| Conversion | `EstimateConversionService` → `JobService` / `OrderService` |
| Service pricing | `ServicesPricebookService.resolve_price` |
| Product pricing | Product/Variant catalog price (same as Orders) |

No duplicate Customer, Product, Service, Job, Order, or pricing engines.

## Tables

Migration `0043_estimates`:

- `estimates`
- `estimate_items` (historical snapshots)
- `estimate_status_history` (append-only)
- `estimate_conversions` (idempotent Job/Order links)
- `estimate_number_counters` (`EST-######`)

## Totals

Server-calculated only:

```text
line_subtotal = unit_price × quantity
line_total = line_subtotal − line_discount + line_tax
estimate.subtotal = Σ line_subtotal
estimate.discount_total = Σ line_discount + estimate_discount
estimate.tax_total = Σ line_tax
estimate.total = subtotal − discount_total + tax_total
```

Client-supplied totals are ignored.

## APIs

Prefix: `/api/admin/crm/estimates`

See [ESTIMATE_LIFECYCLE.md](./ESTIMATE_LIFECYCLE.md), [ESTIMATE_PRICING.md](./ESTIMATE_PRICING.md), [ESTIMATE_CONVERSION.md](./ESTIMATE_CONVERSION.md).

## RBAC

`estimates.read|create|update|delete|send|approve|reject|convert`

AI Agent (default): read/create/update only — not send/approve/reject/convert.

## Frontend

- `/crm/estimates` — list
- `/crm/estimates/new` — create draft
- `/crm/estimates/[id]` — detail, timeline, actions

## Known limitations

- No email/SMS delivery for “send” (status transition only)
- No PDF document generation
- No invoice/payment
- Staging/production verification: see PRODUCTION_READINESS.md
