# Dispatch Realtime (Phase 12)

## Strategy

No WebSocket stack. Dispatch mutations write tenant-scoped rows to `dispatch_events` in the **same database transaction** as the mutation. The board polls:

`GET /api/admin/crm/dispatch/events?after_id=…&limit=…`

Bounds: `limit` default 100, max 500. Cursor is `(created_at, id)` after the anchored event (tenant-scoped).

On relevant event types the UI refreshes the authoritative board.

```text
DB transaction
 ↓
dispatch_events
 ↓
polling feed
 ↓
board reconciliation (GET /board)
```

## Event types

```text
JOB_ASSIGNED
JOB_UNASSIGNED
JOB_REASSIGNED
JOB_STATUS_CHANGED
TECHNICIAN_STATUS_CHANGED
APPOINTMENT_CHANGED
ETA_CHANGED
```

## Security

Events are filtered by authenticated `tenant_id`. Clients cannot subscribe cross-tenant. Identity comes from the session principal — not client-supplied tenant headers.

## Retention

Events are append-only. This phase does **not** ship a purge/archive worker. Polling stays bounded by `limit` + cursor; index `ix_dispatch_events_tenant_created` supports ordered retrieval. Operators should plan retention before high-volume production use.

## Reconciliation

Frontend must tolerate duplicates, gaps, and reconnects by refreshing the board from `GET /board`. Event payloads are hints, not source of truth.
