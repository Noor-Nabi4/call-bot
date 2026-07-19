# Telephony platform API — multi-tenant Twilio + LiveKit SIP

## Run locally

```bash
cd platform
cp .env.local.example .env.local   # or copy from .env.example
uv sync
# Postgres required for production; tests use SQLite in-memory
uv run uvicorn callbot_platform.main:app --reload --port 8000
```

## Docs

- Path A / Path B checklist: `../voice-agent/docs/PHASE2_TELEPHONY_CHECKLIST.md`
- LiveKit Twilio SIP: https://docs.livekit.io/telephony/start/providers/twilio/
