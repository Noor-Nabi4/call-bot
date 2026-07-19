<a href="https://livekit.io/">
  <img src="./.github/assets/livekit-mark.png" alt="LiveKit logo" width="100" height="100">
</a>

# Voice Agent (v1)

Production **voice-only** LiveKit agent using **OpenAI Realtime** speech-to-speech.

## Scope

Version one does exactly this:

> A user joins through a browser (or later a phone call), LiveKit connects them to one Python voice agent, OpenAI Realtime handles speech-to-speech conversation, the agent follows a production system prompt, remembers the current call only, supports natural interruption, records operational metrics, handles failures, and disconnects cleanly.

**Included**

- LiveKit `AgentSession` + OpenAI Realtime model
- Separated prompts (identity, business, voice, safety, call ending)
- Per-call `CallState` (no long-term memory / DB)
- Semantic VAD turn detection and barge-in (`interrupt_response=True`)
- Silence / max-duration lifecycle handling
- Structured operational logs and metrics
- Server-side noise cancellation (Krisp BVC / BVCTelephony)

**Not included (yet)**

RAG, CRM, booking, multi-agent handoffs, Redis memory, analytics dashboards, human handoff.

## Architecture

```text
Caller / Browser
       │
       ▼
LiveKit Room (SIP later)
       │
       ▼
LiveKit AgentSession
       │
       ▼
OpenAI Realtime Model
       │
       ▼
Audio response through LiveKit
```

## Project layout

```text
voice-agent/
├── src/
│   ├── agent.py
│   ├── config.py
│   ├── prompts/
│   ├── session/
│   └── observability/
├── tests/
├── .env.example
├── Dockerfile
└── pyproject.toml
```

## Setup

```bash
cd voice-agent
uv sync
cp .env.example .env.local
```

Fill in `.env.local`:

| Variable | Required | Purpose |
|---|---|---|
| `LIVEKIT_URL` | yes | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | yes | LiveKit API secret |
| `OPENAI_API_KEY` | yes | OpenAI Realtime access |
| `BUSINESS_NAME` | no | Spoken business identity |
| `TENANT_ID` | no | Single-tenant id until multi-tenant dispatch |
| `BUSINESS_HOURS` / `BUSINESS_SERVICES` / … | no | Facts the agent may speak |

Validate without printing secrets:

```bash
uv run python scripts/check_env.py
```
## Run

Console / playground:

```bash
uv run src/agent.py console
```

Dev worker (LiveKit Cloud):

```bash
uv run src/agent.py dev
```

Production worker:

```bash
uv run src/agent.py start
```

## Tests

Unit tests (no live providers required):

```bash
uv run pytest tests/test_config.py tests/test_prompt.py tests/test_state.py tests/test_lifecycle.py tests/test_observability.py -v
```

Behavior evals (requires LiveKit credentials for inference judge models):

```bash
uv run pytest tests/test_agent.py -v
```

## Phase 1 manual verification

Follow [`docs/PHASE1_MANUAL_CHECKLIST.md`](./docs/PHASE1_MANUAL_CHECKLIST.md) for browser/console call tests (greeting, barge-in, silence, disconnect). Complete **10 consecutive successful calls** before Phase 2 telephony.
## Telephony (phase 4)

Only after browser audio is stable: Twilio SIP trunk → LiveKit SIP → this same agent. No telephony code is required for v1 browser audio.

## Docs verified

Implementation follows current LiveKit documentation for:

- [OpenAI Realtime plugin](https://docs.livekit.io/agents/models/realtime/plugins/openai/)
- [Agent sessions](https://docs.livekit.io/agents/logic/sessions/)
- [Turns / interruptions](https://docs.livekit.io/agents/logic/turns/)
- [Realtime metrics](https://docs.livekit.io/reference/recipes/metrics_realtime/)
