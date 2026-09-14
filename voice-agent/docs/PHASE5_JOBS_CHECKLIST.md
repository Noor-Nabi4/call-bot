# Phase 5 — Jobs / dispatch checklist

## Prerequisites

- [ ] Phase 4 booking working (appointment book auto-creates a job)
- [ ] Platform migrated: `alembic upgrade head` includes `0004_jobs_auth`
- [ ] `SESSION_SECRET` set in `platform/.env.local`
- [ ] Web app: `cd web && npm install && npm run dev` (port 3002)

## Bootstrap

- [ ] Create/ensure a tenant exists
- [ ] `POST /auth/bootstrap` with `X-Internal-Token` for first admin
- [ ] Sign in at `http://localhost:3002/login` with tenant slug

## Automated

- [ ] `cd platform && uv run pytest tests/test_jobs_auth.py`

## Operator E2E

- [ ] Voice (or API) books an appointment → `jobs` row appears `scheduled`
- [ ] Dispatcher assigns a technician on `/board` and clicks Dispatch
- [ ] Technician signs in, sees job on `/tech`, starts job, updates checklist, adds notes
- [ ] Technician completes with completion notes → status `completed`, note on job
- [ ] Second tenant cannot see the job (isolation)

## Deferred

- Voice “where’s my tech?” / ETA tool (consumes these APIs later)
