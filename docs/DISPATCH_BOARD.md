# Dispatch Board (Phase 12)

Projection API — not a transactional domain.

## Endpoint

`GET /api/admin/crm/dispatch/board?date=YYYY-MM-DD`

Optional filters: `technician_id`, `status`, `priority`, `assigned=assigned|unassigned`, `q`, `limit`.

## Response

```json
{
  "date": "YYYY-MM-DD",
  "timezone": "IANA",
  "technicians": [],
  "unassigned_jobs": [],
  "assigned_jobs": [],
  "generated_at": "…"
}
```

## Date handling

“Today” uses the tenant business timezone (`ScheduleSettingsRepository.effective_timezone`). The board window is half-open `[local midnight, next local midnight)` converted to UTC. Jobs with `scheduled_starts_at` in that window **or** null schedule appear.

## Frontend

- `/crm/dispatch` — technician columns + unassigned column, HTML5 drag/drop calling `POST …/dispatch/jobs/{id}/assign`. On conflict, the UI refreshes from the board API. Events polled via `GET …/events`.
- Legacy status kanban `/dispatch` — calls consolidated `POST /api/jobs/{id}/assign` (delegates to `DispatchAssignmentService`). On assign failure, the board refreshes so optimistic UI cannot stay wrong.

## Performance

Board loads technicians, statuses, and jobs with `selectinload` — regression test bounds query count for 15 technicians + 100+ jobs (`test_board_n_plus_one_bounded`). Local production-scale EXPLAIN evidence lives in `test_explain_dispatch_hot_paths_production_scale` (PostgreSQL).
