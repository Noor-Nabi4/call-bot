# Call Bot — Voice Playground

Next.js browser playground for the LiveKit `voice-agent` worker (OpenAI Realtime).

Dark branded realtime UI: Fraunces display + IBM Plex Sans, teal accents on
`#07120f`, glass voice panel, and a stepped `/telephony` wizard. LiveKit
session behavior is unchanged (`LiveKitRoom`, `BarVisualizer`,
`VoiceAssistantControlBar`).

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

## Docker

Playground image:

```bash
cd playground
docker build -t call-bot-playground .
docker run --rm -p 3000:3000 --env-file .env.local call-bot-playground
```

Full stack (agent + playground) from repo root:

```bash
# Ensure voice-agent/.env.local and playground/.env.local exist
docker compose up --build
```

- Playground: http://localhost:3000  
- Voice agent joins LiveKit Cloud using credentials from `voice-agent/.env.local`  
- Do not commit secrets into images; pass them via `--env-file` / Compose `env_file`
