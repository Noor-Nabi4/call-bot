# Job Assignment (Phase 10)

Technician assignment is a dedicated action (`POST /api/admin/crm/jobs/{id}/assign`), not a free-form `PATCH` field — this keeps "who is on this job" auditable and keeps the `jobs.assign` permission separate from general `jobs.update`.

## Assignable statuses

A technician may only be (re-)assigned while the job is in `NEW`, `SCHEDULED`, `CONFIRMED`, or `DISPATCHED` (`ASSIGNABLE_STATUSES` in `callbot_platform.crm.jobs.constants`). Attempting to assign a job in `EN_ROUTE`, `ARRIVED`, `IN_PROGRESS`, or a terminal status raises `invalid_transition` (409) — reassigning mid-visit should go through dispatch/cancel-and-recreate workflows, not a silent technician swap.

```python
ASSIGNABLE_STATUSES = {"NEW", "SCHEDULED", "CONFIRMED", "DISPATCHED"}
```

## Unassigning

`POST /jobs/{id}/assign` with `{"technician_id": null}` clears `assigned_technician_id`. Unassign is subject to the same `ASSIGNABLE_STATUSES` gate as assign — clearing a technician while the job is `EN_ROUTE` / `ARRIVED` / `IN_PROGRESS` / terminal raises `invalid_transition`. There is no separate "unassign" endpoint.

## Technician validation

The technician must exist, belong to the same tenant, and be active (`is_active = true`). An inactive or cross-tenant `technician_id` raises `technician_not_found` (404) — the request never leaks whether the technician exists in a different tenant.

## Required-technician guard

Independent of the assign endpoint, `JobTransitionService` blocks entering `DISPATCHED`, `EN_ROUTE`, `ARRIVED`, or `IN_PROGRESS` unless `assigned_technician_id` is already set (`REQUIRES_TECHNICIAN`, see [JOB_LIFECYCLE.md](./JOB_LIFECYCLE.md)). Dispatching an unassigned job always fails closed with `technician_required` — assignment and dispatch are two separate, independently-enforced steps.

## RBAC: resource-aware scope for Technicians

Technicians are granted `jobs.read`, `jobs.update`, `jobs.notes.read/create`, and `jobs.attachments.read/create` at `SCOPE_ASSIGNED` — **not** `jobs.assign` or `jobs.transition` at any scope. A Technician can view and add notes/attachments to their own assigned jobs, and can use the legacy `/api/jobs/{id}/transition` + `/checklist` ops endpoints to progress their own job (dispatch/tech UI), but cannot assign jobs to themselves or other technicians via the CRM API, and cannot delete, archive, or restore jobs.

`AuthorizationService.require_permission` fails closed for `SCOPE_ASSIGNED` grants unless a `ResourceContext` is supplied. Every job-id-scoped CRM endpoint therefore:

1. Fetches the job first (`_get_job_or_404`) — so a Technician gets `404` on a job that isn't theirs, not `403` (no information leak about job existence)
2. Resolves `assigned_technician_user_id` by joining `Technician.user_id` from the job's `assigned_technician_id`
3. Checks the permission with `ResourceContext(tenant_id=..., assigned_technician_user_id=...)`

```python
def _job_resource(session, tenant_id, job: dict) -> ResourceContext:
    tech_id = job.get("assigned_technician_id")
    tech_user_id = None
    if tech_id:
        tech_user_id = session.scalar(
            select(Technician.user_id).where(
                Technician.id == UUID(str(tech_id)), Technician.tenant_id == tenant_id
            )
        )
    return ResourceContext(tenant_id=tenant_id, assigned_technician_user_id=tech_user_id)
```

A Technician whose own `user_id` does not match `assigned_technician_user_id` (i.e. the job is unassigned, or assigned to a different technician) is denied with `403` for scoped actions.

## Concurrent assignment races

Two concurrent `assign` requests for the same job (e.g. two dispatchers assigning different technicians at the same time) are serialized by `SELECT … FOR UPDATE` on the job row in both CRM `JobService.assign` and legacy `JobRepository.assign`; the database guarantees exactly one write wins and the job ends up consistently assigned to one technician — verified in `tests/test_jobs_pg_concurrency.py::test_concurrent_assign_race_single_winner_consistency` against real Postgres. Archived jobs cannot be assigned (`job_archived`).

## Dispatch board vs CRM assignment

The Dispatch board (`/dispatch`, legacy `/api/jobs/{id}/assign`) and the Phase 10 CRM job detail page (`/crm/jobs/{id}`, `/api/admin/crm/jobs/{id}/assign`) both call into the same underlying `assigned_technician_id` column and the same `ASSIGNABLE_STATUSES` guard — there is no divergent assignment logic between the operational kanban board and the CRM record view.
