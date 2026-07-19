# Call Bot Ops

Tenant-scoped operations console: dashboard overview, dispatch board, and
technician mobile UI.

Premium ops product: warm-gray canvas, white surfaces, teal brand `#1f6f5b`,
IBM Plex Sans/Mono, left sidebar navigation. Shared UI under `src/components/ui/`
and `src/components/ops/`.

## Routes

| Path | Purpose |
|------|---------|
| `/dashboard` | Default landing after login (ops overview) |
| `/dispatch` | Kanban job assignment workspace |
| `/board` | Redirects to `/dispatch` (compat) |
| `/tech` | Technician mobile jobs |

## Run

```bash
cd ops
cp .env.example .env.local
npm install
npm run dev   # http://localhost:3001
```

Platform API must be running on `:8000` with `SESSION_SECRET` set and CORS allowing `http://localhost:3001`.

## Bootstrap first admin

```bash
curl -X POST http://localhost:8000/auth/bootstrap \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $INTERNAL_SERVICE_TOKEN" \
  -d '{"tenant_id":"<uuid>","email":"admin@acme.test","password":"password123","name":"Ops Admin"}'
```

Then sign in at `/login` with the tenant slug.
