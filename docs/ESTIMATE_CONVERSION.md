# Estimate Conversion

Only `APPROVED`, non-expired, non-archived estimates can convert.

```text
POST /api/admin/crm/estimates/{id}/convert
{ "target_type": "JOB" | "ORDER" }
```

Idempotency-Key supported.

## Targets

| Target | Mapping |
|--------|---------|
| JOB | `JobService.create` — first SERVICE line’s `service_id` when present; title/description from estimate |
| ORDER | `OrderService.create` — PRODUCT lines only (whole-number quantities); estimate-level discount applied |

CUSTOM lines are quote-only and are not pushed into Orders.

## Idempotency

`estimate_conversions` enforces:

- unique `(tenant_id, estimate_id)` — one conversion per estimate
- unique `(tenant_id, idempotency_key)` with request hash

Same key + same payload → original result.  
Same key + different payload → `idempotency_conflict`.

Inventory is **not** touched by estimate create/approve. Order conversion uses the existing Order lifecycle for inventory.
