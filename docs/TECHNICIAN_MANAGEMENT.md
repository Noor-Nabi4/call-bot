# Technician Management (Phase 12)

Phase 12 **reuses** the existing `technicians` model and Phase 11 availability tables. There is no second technician catalog.

## Profile

`technicians`: `display_name`, `phone`, `is_active`, location ping fields, timestamps, `tenant_id`, linked `tenant_users` account.

Create via `POST /api/technicians` (`technicians.manage`). New active technicians receive an operational status row (`AVAILABLE`).

## Skills / service areas / schedule

Managed under `/api/admin/crm` Phase 11 endpoints (`TechnicianAvailabilityService`):

- skills + technician_skills + service_required_skills
- service_areas + technician_service_areas
- schedule periods, breaks, time off

## Service categories

Pricebook `service_categories` remain authoritative. Technician eligibility for a job/service is enforced through **required skills** on the service (and optional service-area match). No separate technician↔category join table.

## Ops composite view

`GET /api/admin/crm/dispatch/technicians/{id}` returns profile + status + skills + areas + schedule + breaks + time off + status history for the dispatch UI.
