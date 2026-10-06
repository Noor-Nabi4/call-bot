# Dispatch Architecture (Phase 12)

Dispatch is a **thin operations layer** over existing Jobs, Technicians, Appointments, and Phase 11 scheduling. It does not duplicate those domains.

## Assignment architecture (authoritative)

```text
CRM Dispatch UI (/crm/dispatch)
Legacy Dispatch UI (/dispatch)
        │
        ▼
Dispatch / Jobs HTTP APIs
        │
        ▼
DispatchAssignmentService   ← single mutation implementation
        │
        ▼
Job row (authoritative state)
        ├── FOR UPDATE
        ├── eligibility (skills, areas, schedule, breaks, time off, appointments, ops status)
        ├── job_assignment_history (append-only)
        ├── write_audit (success-only)
        └── dispatch_events (same transaction)
```

| Path | HTTP | Mutation |
|------|------|----------|
| CRM dispatch board | `POST /api/admin/crm/dispatch/jobs/{id}/assign` | `DispatchAssignmentService` |
| CRM jobs | `POST /api/admin/crm/jobs/{id}/assign` → `JobService.assign` | `DispatchAssignmentService` |
| Legacy ops kanban | `POST /api/jobs/{id}/assign` → `JobRepository.assign` | `DispatchAssignmentService` |
| Job create with technician | `JobService.create(..., technician_id=)` | create then `DispatchAssignmentService.assign` |

There is no second assignment engine. Appointment assignment remains Phase 11 (`AppointmentService`) and does not write job assignment history.

## Authoritative flow

```text
Board / drag-drop (advisory UI)
        ↓
DispatchAssignmentService.assign / TechnicianStatusService.transition
        ↓
Eligibility revalidation (skills, areas, schedule, appointments, ops status)
        ↓
SELECT … FOR UPDATE on job / status row
        ↓
Mutation + assignment/status history + audit + dispatch_events
        ↓
Commit
```

Availability/board responses and polling events are **never** authoritative.

## Reuse decisions

| Concept | Decision |
|---------|----------|
| Technicians | Reuse `technicians` (`is_active`, profile, phone) |
| Skills / areas / schedule / breaks / time off | Reuse Phase 11 tables + `TechnicianAvailabilityService` |
| Service categories | Reuse pricebook `service_categories` via `services.category_id`; eligibility via required skills (no tech↔category table) |
| Jobs | Reuse `jobs.assigned_technician_id`; extend with `assigned_at`, `assigned_by`, `eta*` |
| Appointments | Conflict check against active appointment ranges for technician |
| RBAC | Reuse `jobs.assign`; add `dispatch.read`, `dispatch.status.update` |
| Audit | Reuse `write_audit` / `TelephonyAuditEvent` |
| Realtime | No WebSocket — tenant-scoped `dispatch_events` polled by the board |

## New tables

- `technician_operational_status` — one row per technician
- `technician_status_history` — append-only
- `job_assignment_history` — append-only (+ optional idempotency key)
- `dispatch_events` — append-only polling feed

Migration: `0042_dispatch` (down from `0041_appointments_scheduling`).

## APIs

Prefix: `/api/admin/crm/dispatch`

- `GET /board`
- `GET /events`
- `POST /jobs/{id}/assign`
- `GET /jobs/{id}/assignment-history`
- `GET/POST /technicians/{id}/status`
- `GET /technicians/{id}/status-history`
- `GET /technicians/{id}` (ops composite)

## Known limitations

- Realtime is **polling**, not WebSocket
- Overnight business hours remain unsupported (Phase 11 contract)
- `dispatch_events` are append-only with **no retention/cleanup job** in this phase; retrieval is bounded (`limit` ≤ 500) and indexed by `(tenant_id, created_at, id)`
- Staging / production verification: see `PRODUCTION_READINESS.md`
