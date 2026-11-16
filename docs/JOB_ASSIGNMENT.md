# Job Assignment (Phase 10 + Phase 12 consolidation)

Technician assignment is a dedicated action — not a free-form `PATCH` field — so "who is on this job" stays auditable and `jobs.assign` stays separate from general `jobs.update`.

## Authoritative service

All job assignment mutations go through `DispatchAssignmentService`:

```text
All assignment paths
        ↓
DispatchAssignmentService
        ↓
authoritative Job mutation (+ history + audit + dispatch_events)
```

| Caller | Entry |
|--------|--------|
| CRM dispatch | `POST /api/admin/crm/dispatch/jobs/{id}/assign` |
| CRM jobs | `JobService.assign` → service |
| Legacy ops | `POST /api/jobs/{id}/assign` → `JobRepository.assign` → service |
| Create-with-tech | `JobService.create(..., technician_id=)` → service after insert |

## Assignable statuses

A technician may only be (re-)assigned while the job is in `NEW`, `SCHEDULED`, `CONFIRMED`, or `DISPATCHED` (`ASSIGNABLE_STATUSES` in `callbot_platform.crm.jobs.constants`). Attempting to assign a job in `EN_ROUTE`, `ARRIVED`, `IN_PROGRESS`, or a terminal status raises `invalid_transition` (409).

## Unassigning

`POST …/assign` with `{"technician_id": null}` clears `assigned_technician_id` (CRM/dispatch). Legacy `/api/jobs/{id}/assign` still requires a non-null UUID body for backwards compatibility; unassign via CRM/dispatch APIs. Unassign is subject to the same assignable-status gate.

## Eligibility (Phase 12)

Before mutation, `AssignmentEligibility` validates (when facts exist):

- technician tenant + `is_active`
- operational status not in unassignable set (`OFFLINE`, `ON_BREAK`, …)
- required skills / service
- service area vs job location
- schedule window, breaks, time off
- overlapping active appointments

## History / audit / events

Successful assign / reassign / unassign writes:

- append-only `job_assignment_history` (previous → new technician, actor, reason, timestamps)
- success-only `write_audit` (`job_assigned` / `job_reassigned` / `job_unassigned`)
- `dispatch_events` (`JOB_ASSIGNED` / `JOB_REASSIGNED` / `JOB_UNASSIGNED`)

Rejected mutations write none of the above. Idempotent retries with the same key do not duplicate history.

## Required-technician guard

Independent of assign, `JobTransitionService` blocks entering `DISPATCHED`, `EN_ROUTE`, `ARRIVED`, or `IN_PROGRESS` unless `assigned_technician_id` is set (`REQUIRES_TECHNICIAN`).

## Concurrent assignment

Same-job assign races are serialized by `SELECT … FOR UPDATE` on the job row. Verified in `tests/test_dispatch_pg_concurrency.py` and `tests/test_jobs_pg_concurrency.py` against real Postgres.

## RBAC

- Assign: `jobs.assign`
- Board / events / history read: `dispatch.read`
- Status updates: `dispatch.status.update` (technicians may update own status)
- AI Agent: `dispatch.read` + `technicians.read`; **not** `jobs.assign` / `dispatch.status.update`

See [DISPATCH_ARCHITECTURE.md](./DISPATCH_ARCHITECTURE.md).
