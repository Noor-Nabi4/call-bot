# VoxPilot

Multi-tenant AI voice platform for service businesses and call centers
(**LiveKit + OpenAI Realtime** voice agent).

## Docs

- Product / phase plan: [`TASKS.md`](./TASKS.md)
- Voice agent details: [`voice-agent/README.md`](./voice-agent/README.md)
- Phase 2 telephony checklist: [`voice-agent/docs/PHASE2_TELEPHONY_CHECKLIST.md`](./voice-agent/docs/PHASE2_TELEPHONY_CHECKLIST.md)
- Phase 3 CRM checklist: [`voice-agent/docs/PHASE3_CRM_CHECKLIST.md`](./voice-agent/docs/PHASE3_CRM_CHECKLIST.md)
- Phase 4 booking checklist: [`voice-agent/docs/PHASE4_BOOKING_CHECKLIST.md`](./voice-agent/docs/PHASE4_BOOKING_CHECKLIST.md)
- Phase 5 jobs checklist: [`voice-agent/docs/PHASE5_JOBS_CHECKLIST.md`](./voice-agent/docs/PHASE5_JOBS_CHECKLIST.md)
- Platform API: [`platform/README.md`](./platform/README.md)
- Web (marketing + ops): [`web/README.md`](./web/README.md)

## Architecture decisions (Phase 0)

| Decision | Choice |
|----------|--------|
| Deploy target | **LiveKit Cloud agent worker** (`uv run src/agent.py start` / `lk agent` deploy). Self-host only if required later. |
| Tenant runtime | **Shared worker**; resolve `tenant_id` at dispatch (Phase 2–3). Phase 0/1 may set optional `TENANT_ID` in env for a single business. |

## Quick start (voice agent)

```bash
cd voice-agent
uv sync
cp .env.example .env.local   # if you do not already have one
# Fill LIVEKIT_* and OPENAI_API_KEY (required)
uv run python scripts/check_env.py
uv run src/agent.py console  # local mic test
# or
uv run src/agent.py dev      # LiveKit Cloud dev worker
```

Unit tests (no live providers):

```bash
cd voice-agent
uv run pytest tests/test_config.py tests/test_prompt.py tests/test_state.py tests/test_lifecycle.py -v
```

## Production hosts

| Service | URL |
|---|---|
| Web (marketing + ops) | `https://callandflow.com` (`www` redirects) |
| Platform API | `https://api.callandflow.com` |
| Voice agent | Self-host worker **or** LiveKit Cloud |
| LiveKit media | Cloud **or** self-host SFU |

### Easy install (recommended)

Interactive wizard: domains, secrets, nginx, certbot, docker compose (web + API + agent + optional self-hosted LiveKit).

```bash
# On the server — DNS A records first
sudo bash deploy/install.sh
```

Details: [`deploy/README.md`](./deploy/README.md).

### Manual install

Copy `.env.production.example` in `web/`, `platform/`, and `voice-agent/`. Do not commit filled files.

```bash
docker compose -f docker-compose.production.yml up -d --build
# or after the installer:
docker compose -f docker-compose.selfhost.yml up -d --build
```

Stripe webhook: `https://api.callandflow.com/billing/webhooks/stripe`.

## Repo layout

```text
call-bot/
├── TASKS.md                 # phased product plan
├── docker-compose.yml       # redis + voice-agent
├── .github/workflows/       # CI
├── platform/                # FastAPI telephony + CRM + scheduling + jobs
├── voice-agent/             # LiveKit voice worker (v1) + Dockerfile
└── web/                     # Marketing + ops console (Next.js)
```

## Quick start (web)

```bash
cd web
cp .env.example .env.local
npm install
npm run dev   # http://localhost:3002
```

Marketing landing is `/`. Embedded voice demo is `/#demo` (tenant-less). Sign in at `/login`. Tenant-specific voice testing is `/playground`.

Bootstrap the first tenant admin via `POST /auth/bootstrap` (see `web/README.md`).

## Quick start (platform telephony API)

```bash
cd platform
uv sync
cp .env.example .env.local
# Fill DATABASE_URL, LIVEKIT_*, TWILIO_* (Path B), secrets
uv run uvicorn callbot_platform.main:app --port 8000
```

Phone onboarding and test calls are managed from Ops (`/phones`, `/playground`).

## Docker

```bash
# from repo root (requires voice-agent/.env.local)
docker compose up --build
```

Compose includes Redis for the voice-agent shared Agent Profile cache (`REDIS_URL`).

## Secrets

Never commit `.env` / `.env.local`. Only `.env.example` (names + sample non-secret facts) is tracked.
