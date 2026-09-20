# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS base

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV PYTHONDONTWRITEBYTECODE=1

FROM base AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY alembic.ini ./
COPY src ./src
RUN uv sync --locked --no-dev

FROM base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
  && rm -rf /var/lib/apt/lists/*

ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/app" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser

WORKDIR /app
COPY --from=build --chown=appuser:appuser /app /app
COPY --chown=appuser:appuser scripts/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

USER appuser

ENV PATH="/app/.venv/bin:$PATH"
ENV ENVIRONMENT=production
ENV COOKIE_SECURE=true
ENV ALLOW_ENV_TENANT_FALLBACK=false
ENV PLATFORM_API_HOST=0.0.0.0
ENV PLATFORM_API_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
