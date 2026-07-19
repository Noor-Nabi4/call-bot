# Call Bot — Voice Playground

Next.js browser playground for the LiveKit `voice-agent` worker (OpenAI Realtime).

## Prerequisites

1. LiveKit Cloud project credentials
2. Voice worker running:

```bash
cd ../voice-agent
uv sync
uv run python scripts/check_env.py
uv run src/agent.py dev
```

## Setup

```bash
cd playground
cp .env.example .env.local
# Fill LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and click **Start call**.

## How it works

```text
Browser playground
  → POST /api/token (server mints JWT + agent dispatch)
  → LiveKit room
  → explicit dispatch to agent_name=voice-agent
  → Python Realtime agent answers
```

The token route is for **local playground use**. Do not expose it publicly without authentication.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Local playground |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | ESLint |
