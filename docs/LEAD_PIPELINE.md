# Lead Pipeline

## Statuses (ordered)

```text
NEW → QUALIFIED → CONTACTED → BOOKED → WON
                              ↘ LOST (from NEW/QUALIFIED/CONTACTED/BOOKED)
LOST → NEW   (documented reopen only)
```

`BOOKED` is a pipeline state only. Scheduling/appointments are **out of scope** for Phase 8.

**WON ≠ converted.** Conversion is a separate explicit operation (see LEAD_CONVERSION.md).

## Valid transitions

| From | To |
|------|-----|
| NEW | QUALIFIED, LOST |
| QUALIFIED | CONTACTED, LOST |
| CONTACTED | BOOKED, LOST |
| BOOKED | WON, LOST |
| LOST | NEW |
| WON | *(none)* |

Raw `PATCH` with `status` is rejected (`use_transition`). UI moves must call `POST /leads/{id}/transition`.

## Transition service

`LeadService.transition_status`:

1. Tenant-scoped load + `FOR UPDATE`
2. Validate archived / current / target
3. Update status
4. Record `STATUS_CHANGED` (+ notable type CONTACTED/BOOKED/WON/LOST)
5. Audit `lead_status_changed`
6. Commit atomically with the request transaction

Rejected transitions create **no** STATUS_CHANGED activity.

## Pipeline UI

`/crm/leads` — Pipeline + List views. Column counts from `GET /leads/pipeline/counts` (not client-side full-table counts). Optimistic UI rolls back on transition failure; double-submit guarded while a transition is in flight.
