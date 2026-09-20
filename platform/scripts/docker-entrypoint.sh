#!/bin/sh
set -eu

uv run python -c "from callbot_platform.config import get_settings, require_production_settings; require_production_settings(get_settings())"
uv run alembic upgrade head
exec uv run uvicorn callbot_platform.main:app \
  --host "${PLATFORM_API_HOST:-0.0.0.0}" \
  --port "${PLATFORM_API_PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
