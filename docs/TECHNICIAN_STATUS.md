# Technician Operational Status (Phase 12)

Technician operational status is **separate** from Job status.

## Statuses

```text
AVAILABLE | BUSY | EN_ROUTE | ARRIVED | ON_BREAK | OFFLINE
```

## Transition matrix

Valid edges (enforced by `TechnicianStatusService`):

```text
AVAILABLE → BUSY | ON_BREAK | OFFLINE
BUSY → AVAILABLE | EN_ROUTE | ON_BREAK | OFFLINE
EN_ROUTE → ARRIVED | AVAILABLE | OFFLINE
ARRIVED → BUSY | AVAILABLE
ON_BREAK → AVAILABLE | OFFLINE
OFFLINE → AVAILABLE
```

Invalid transitions raise `status_transition_invalid` with **no** history row and **no** success audit.

## Storage

- Current: `technician_operational_status` (unique per tenant+technician)
- History: `technician_status_history` (append-only)

## Authorization

- Dispatchers: `dispatch.status.update`
- Technicians: may update **own** status only (matched via `technicians.user_id`)

## Dispatch eligibility

`OFFLINE` and `ON_BREAK` reject new job assignments (`technician_unavailable`). Missing status rows (legacy) are treated as AVAILABLE for assignment.
