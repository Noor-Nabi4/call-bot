# Availability Engine (Phase 11)

`AvailabilityEngine` computes candidate windows dynamically. It does **not** persist slot rows.

## Pipeline

1. Resolve tenant timezone + duration (service `duration_minutes` or request)
2. Expand business or emergency weekly hours over the date range
3. Remove holidays
4. For each eligible active technician: intersect schedule, subtract breaks/time-off/appointments
5. Filter skills and service area
6. Fit duration into remaining windows (slot step from settings `slot_minutes`)
7. Return advisory slots `{starts_at, ends_at, technician_id, technician_name}`

## Authoritative booking

Create/reschedule re-checks conflicts inside the transaction and relies on PostgreSQL exclusion for same-technician overlaps. A previously returned “available” slot may be rejected with `slot_conflict` / integrity error. The CRM availability UI refreshes slots on booking conflict rather than treating the advisory response as a reservation.

## Service area matching

Deterministic string match only (no GIS/radius):

1. Technician areas of type `POSTAL_CODE` → customer location `postal_code`
2. `CITY` → `city`
3. `REGION` → `state`

All lookups are tenant-scoped. Cross-tenant area/skill IDs fail closed.

## Emergency

`is_emergency=true` selects emergency weekly hours. It does **not** bypass double-booking protection, skills, or service areas.
