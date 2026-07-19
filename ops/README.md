# Call Bot Ops

Tenant-scoped dispatch board and technician mobile UI.

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
