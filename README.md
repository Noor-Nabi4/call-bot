# Call Bot

Multi-tenant field-service platform (ServiceTitan-style), starting with a
production **LiveKit + OpenAI Realtime** voice agent.

## Docs

- Product / phase plan: [`TASKS.md`](./TASKS.md)
- Voice agent details: [`voice-agent/README.md`](./voice-agent/README.md)

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

## Quick start (browser playground)

With the voice worker running (`uv run src/agent.py dev`):

```bash
cd playground
cp .env.example .env.local
# Fill LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
npm install
npm run dev
```

Open http://localhost:3000 and click **Start call**.

Unit tests (no live providers):

```bash
cd voice-agent
uv run pytest tests/test_config.py tests/test_prompt.py tests/test_state.py tests/test_lifecycle.py -v
```

## Repo layout

```text
call-bot/
├── TASKS.md                 # phased product plan
├── docker-compose.yml       # voice-agent + playground
├── .github/workflows/       # CI
├── voice-agent/             # LiveKit voice worker (v1) + Dockerfile
└── playground/              # Next.js browser playground + Dockerfile
```

## Docker

```bash
# from repo root (requires both .env.local files)
docker compose up --build
```

Playground only:

```bash
cd playground
docker build -t call-bot-playground .
docker run --rm -p 3000:3000 --env-file .env.local call-bot-playground
```

## Secrets

Never commit `.env` / `.env.local`. Only `.env.example` (names + sample non-secret facts) is tracked.
