#!/usr/bin/env bash
# VoxPilot interactive production installer.
# Generates env files, nginx configs, docker compose, optional TLS + start.
#
# Usage (from repo root or this directory):
#   sudo bash deploy/install.sh
#   bash deploy/install.sh --yes   # non-interactive only if deploy/answers.env exists
#
# Safe defaults: never prints secret values; chmod 600 on env files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATES="${SCRIPT_DIR}/templates"
OUT_DIR="${SCRIPT_DIR}/generated"
ANSWERS_FILE="${SCRIPT_DIR}/answers.env"
COMPOSE_OUT="${REPO_ROOT}/docker-compose.selfhost.yml"

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
NC=$'\033[0m'

log()  { printf '%s\n' "$*"; }
info() { printf '%s%s%s\n' "${CYAN}" "$*" "${NC}"; }
ok()   { printf '%s%s%s\n' "${GREEN}" "$*" "${NC}"; }
warn() { printf '%s%s%s\n' "${YELLOW}" "$*" "${NC}"; }
err()  { printf '%s%s%s\n' "${RED}" "$*" "${NC}" >&2; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    err "Missing required command: $1"
    exit 1
  }
}

rand_hex() {
  openssl rand -hex "${1:-32}"
}

rand_api_key() {
  # LiveKit-style API key prefix
  printf 'API%s' "$(openssl rand -hex 10)"
}

prompt() {
  # prompt VAR "Question" "default"
  local __var="$1"
  local __q="$2"
  local __def="${3:-}"
  local __val=""
  if [[ -n "${__def}" ]]; then
    read -r -p "${__q} [${__def}]: " __val || true
    __val="${__val:-$__def}"
  else
    read -r -p "${__q}: " __val || true
  fi
  printf -v "${__var}" '%s' "${__val}"
}

prompt_secret() {
  # prompt_secret VAR "Question" ["auto-generate-if-empty"]
  local __var="$1"
  local __q="$2"
  local __auto="${3:-}"
  local __val=""
  read -r -s -p "${__q}: " __val || true
  echo
  if [[ -z "${__val}" && "${__auto}" == "auto" ]]; then
    __val="$(rand_hex 32)"
    ok "  → generated (not shown)"
  fi
  printf -v "${__var}" '%s' "${__val}"
}

prompt_yn() {
  local __var="$1"
  local __q="$2"
  local __def="${3:-y}"
  local __val=""
  local __hint="y/N"
  [[ "${__def}" == "y" || "${__def}" == "Y" ]] && __hint="Y/n"
  read -r -p "${__q} [${__hint}]: " __val || true
  __val="${__val:-$__def}"
  case "${__val}" in
    y|Y|yes|YES) printf -v "${__var}" 'y' ;;
    *) printf -v "${__var}" 'n' ;;
  esac
}

require_nonempty() {
  local name="$1" val="$2"
  if [[ -z "${val}" ]]; then
    err "Required value missing: ${name}"
    exit 1
  fi
}

render_tpl() {
  # envsubst-style replace of ${VAR} from current shell exports
  local src="$1"
  local dest="$2"
  python3 - "$src" "$dest" <<'PY'
import os, re, sys
src, dest = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()
pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

def repl(m):
    key = m.group(1)
    if key not in os.environ:
        raise SystemExit(f"template var missing: {key}")
    return os.environ[key]

open(dest, "w", encoding="utf-8").write(pattern.sub(repl, text))
PY
}

write_file() {
  local path="$1"
  local mode="${2:-644}"
  mkdir -p "$(dirname "${path}")"
  cat > "${path}"
  chmod "${mode}" "${path}"
}

ensure_dirs() {
  mkdir -p "${OUT_DIR}/nginx" "${OUT_DIR}/livekit" /var/www/certbot 2>/dev/null || mkdir -p "${OUT_DIR}/nginx" "${OUT_DIR}/livekit"
}

banner() {
  cat <<'EOF'

╔══════════════════════════════════════════════════╗
║     Call & Flow production installer             ║
║     web + API + agent (+ optional LiveKit SFU)   ║
║     Postgres + Redis: on HOST (not Docker)       ║
╚══════════════════════════════════════════════════╝

EOF
}

urlencode() {
  python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

load_answers_if_any() {
  if [[ -f "${ANSWERS_FILE}" ]]; then
    warn "Loading non-secret defaults from ${ANSWERS_FILE}"
    # shellcheck disable=SC1090
    set -a
    # only allow KEY=VALUE lines, no command substitution
    while IFS= read -r line || [[ -n "${line}" ]]; do
      [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
      if [[ "${line}" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
        export "${line?}"
      fi
    done < "${ANSWERS_FILE}"
    set +a
  fi
}

save_answers() {
  # Persist non-secret answers for re-runs (NOT secrets)
  write_file "${ANSWERS_FILE}" 600 <<EOF
# Non-secret installer answers — safe-ish to keep on the server.
# Secrets stay in platform|web|voice-agent/.env.production only.
LIVEKIT_MODE=${LIVEKIT_MODE}
LIVEKIT_MODE_CHOICE=${LIVEKIT_MODE_CHOICE:-}
WEB_DOMAIN=${WEB_DOMAIN}
API_DOMAIN=${API_DOMAIN}
LIVEKIT_DOMAIN=${LIVEKIT_DOMAIN}
LIVEKIT_URL=${LIVEKIT_URL}
LIVEKIT_SIP_HOST=${LIVEKIT_SIP_HOST}
AGENT_NAME=${AGENT_NAME}
PG_DB=${PG_DB}
PG_USER=${PG_USER}
PG_PORT=${PG_PORT}
REDIS_PORT=${REDIS_PORT}
REDIS_HOST_FOR_CONTAINERS=${REDIS_HOST_FOR_CONTAINERS}
SETUP_HOST_SERVICES=${SETUP_HOST_SERVICES}
INSTALL_NGINX=${INSTALL_NGINX}
INSTALL_CERTBOT=${INSTALL_CERTBOT}
START_STACK=${START_STACK}
CERTBOT_EMAIL=${CERTBOT_EMAIL}
EOF
  ok "Saved non-secret answers → ${ANSWERS_FILE}"
}

check_prereqs() {
  need_cmd openssl
  need_cmd python3
  need_cmd docker
  if ! docker compose version >/dev/null 2>&1; then
    err "docker compose plugin required"
    exit 1
  fi
}

collect_inputs() {
  info "=== Domains ==="
  prompt WEB_DOMAIN "Web domain (apex; www redirects here)" "${WEB_DOMAIN:-callandflow.com}"
  prompt API_DOMAIN "API domain" "${API_DOMAIN:-api.callandflow.com}"
  require_nonempty WEB_DOMAIN "${WEB_DOMAIN}"
  require_nonempty API_DOMAIN "${API_DOMAIN}"
  WEB_WWW_DOMAIN="www.${WEB_DOMAIN}"
  info "  www → https://${WEB_DOMAIN}  (also: ${WEB_WWW_DOMAIN})"

  info ""
  info "=== LiveKit mode ==="
  log "  1) LiveKit Cloud  (agent can also run on this server)"
  log "  2) Self-host LiveKit SFU container (uses HOST Redis)"
  prompt LIVEKIT_MODE_CHOICE "Choose 1 or 2" "${LIVEKIT_MODE_CHOICE:-2}"
  case "${LIVEKIT_MODE_CHOICE}" in
    1) LIVEKIT_MODE="cloud" ;;
    2) LIVEKIT_MODE="selfhost" ;;
    *) err "Invalid LiveKit mode"; exit 1 ;;
  esac

  AGENT_NAME="${AGENT_NAME:-voice-agent}"

  if [[ "${LIVEKIT_MODE}" == "cloud" ]]; then
    prompt LIVEKIT_URL "LIVEKIT_URL (wss://....livekit.cloud)" "${LIVEKIT_URL:-}"
    prompt LIVEKIT_API_KEY "LIVEKIT_API_KEY" "${LIVEKIT_API_KEY:-}"
    prompt_secret LIVEKIT_API_SECRET "LIVEKIT_API_SECRET (hidden)"
    prompt LIVEKIT_SIP_HOST "LIVEKIT_SIP_HOST (xxx.sip.livekit.cloud, blank ok)" "${LIVEKIT_SIP_HOST:-}"
    prompt LIVEKIT_DOMAIN "LiveKit public domain (unused for cloud; press enter)" "${LIVEKIT_DOMAIN:-}"
    LIVEKIT_DOMAIN="${LIVEKIT_DOMAIN:-unused.invalid}"
  else
    prompt LIVEKIT_DOMAIN "LiveKit WSS domain" "${LIVEKIT_DOMAIN:-livekit.${WEB_DOMAIN}}"
    LIVEKIT_URL="wss://${LIVEKIT_DOMAIN}"
    if [[ -z "${LIVEKIT_API_KEY:-}" ]]; then
      LIVEKIT_API_KEY="$(rand_api_key)"
      ok "Generated LIVEKIT_API_KEY"
    else
      prompt LIVEKIT_API_KEY "LIVEKIT_API_KEY" "${LIVEKIT_API_KEY}"
    fi
    if [[ -z "${LIVEKIT_API_SECRET:-}" ]]; then
      LIVEKIT_API_SECRET="$(rand_hex 32)"
      ok "Generated LIVEKIT_API_SECRET"
    else
      prompt_secret LIVEKIT_API_SECRET "LIVEKIT_API_SECRET (hidden, empty=keep)"
    fi
    prompt LIVEKIT_SIP_HOST "LIVEKIT_SIP_HOST (self-host SIP later; blank ok)" "${LIVEKIT_SIP_HOST:-}"
  fi

  require_nonempty LIVEKIT_URL "${LIVEKIT_URL}"
  require_nonempty LIVEKIT_API_KEY "${LIVEKIT_API_KEY}"
  require_nonempty LIVEKIT_API_SECRET "${LIVEKIT_API_SECRET}"

  info ""
  info "=== Postgres + Redis on HOST (not Docker) ==="
  log "  App containers use host.docker.internal → this machine."
  prompt_yn SETUP_HOST_SERVICES "Install/configure PostgreSQL + Redis on this host now?" "${SETUP_HOST_SERVICES:-y}"
  prompt PG_DB "Postgres database name" "${PG_DB:-call_bot}"
  prompt PG_USER "Postgres user" "${PG_USER:-callbot}"
  prompt PG_PORT "Postgres port" "${PG_PORT:-5432}"
  prompt_secret PG_PASSWORD "Postgres password (empty = auto)" auto
  prompt REDIS_PORT "Redis port" "${REDIS_PORT:-6379}"
  prompt_secret REDIS_PASSWORD "Redis password (empty = auto)" auto
  REDIS_HOST_FOR_CONTAINERS="${REDIS_HOST_FOR_CONTAINERS:-host.docker.internal}"

  HOST_GATEWAY_NAME="${REDIS_HOST_FOR_CONTAINERS}"
  PG_PASSWORD_ENC="$(urlencode "${PG_PASSWORD}")"
  REDIS_PASSWORD_ENC="$(urlencode "${REDIS_PASSWORD}")"
  DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASSWORD_ENC}@${HOST_GATEWAY_NAME}:${PG_PORT}/${PG_DB}"
  REDIS_URL="redis://:${REDIS_PASSWORD_ENC}@${HOST_GATEWAY_NAME}:${REDIS_PORT}/0"
  ok "  DATABASE_URL → ${HOST_GATEWAY_NAME}:${PG_PORT}/${PG_DB}"
  ok "  REDIS_URL → ${HOST_GATEWAY_NAME}:${REDIS_PORT}"

  info ""
  info "=== Shared secrets (empty = auto-generate) ==="
  prompt_secret SESSION_SECRET "SESSION_SECRET" auto
  prompt_secret CREDENTIALS_ENCRYPTION_KEY "CREDENTIALS_ENCRYPTION_KEY" auto
  prompt_secret METADATA_HMAC_SECRET "METADATA_HMAC_SECRET" auto
  prompt_secret INTERNAL_SERVICE_TOKEN "INTERNAL_SERVICE_TOKEN" auto

  info ""
  info "=== OpenAI (required for voice agent) ==="
  prompt_secret OPENAI_API_KEY "OPENAI_API_KEY (hidden)"
  require_nonempty OPENAI_API_KEY "${OPENAI_API_KEY}"

  info ""
  info "=== Stripe (required — platform refuses empty in production) ==="
  prompt_secret STRIPE_SECRET_KEY "STRIPE_SECRET_KEY (sk_live_... or sk_test_...)"
  prompt_secret STRIPE_WEBHOOK_SECRET "STRIPE_WEBHOOK_SECRET (whsec_...)"
  require_nonempty STRIPE_SECRET_KEY "${STRIPE_SECRET_KEY}"
  require_nonempty STRIPE_WEBHOOK_SECRET "${STRIPE_WEBHOOK_SECRET}"

  info ""
  info "=== Twilio (optional — press enter to skip) ==="
  prompt TWILIO_ACCOUNT_SID "TWILIO_ACCOUNT_SID" "${TWILIO_ACCOUNT_SID:-}"
  if [[ -n "${TWILIO_ACCOUNT_SID}" ]]; then
    prompt_secret TWILIO_AUTH_TOKEN "TWILIO_AUTH_TOKEN (hidden)"
  else
    TWILIO_AUTH_TOKEN=""
  fi

  info ""
  info "=== Nginx / TLS / start ==="
  prompt_yn INSTALL_NGINX "Install nginx site configs to /etc/nginx/sites-available?" "y"
  prompt_yn INSTALL_CERTBOT "Obtain Let's Encrypt certs with certbot?" "y"
  prompt CERTBOT_EMAIL "Certbot email" "${CERTBOT_EMAIL:-admin@${WEB_DOMAIN}}"
  prompt_yn START_STACK "Build and start docker compose now?" "y"
  prompt_yn OPEN_FIREWALL "Print firewall ports to open (ufw hints)?" "y"
}

export_template_vars() {
  export WEB_DOMAIN API_DOMAIN LIVEKIT_DOMAIN LIVEKIT_MODE
  export LIVEKIT_URL LIVEKIT_API_KEY LIVEKIT_API_SECRET LIVEKIT_SIP_HOST
  export AGENT_NAME
  export REDIS_HOST_FOR_CONTAINERS REDIS_PORT

  if [[ "${LIVEKIT_MODE}" == "selfhost" ]]; then
    LIVEKIT_SERVICE_BLOCK="$(cat <<EOF
  livekit:
    image: livekit/livekit-server:latest
    restart: unless-stopped
    command: ["--config", "/etc/livekit.yaml"]
    volumes:
      - ./deploy/generated/livekit/livekit.yaml:/etc/livekit.yaml:ro
    extra_hosts:
      - "host.docker.internal:host-gateway"
    ports:
      - "7880:7880"
      - "7881:7881"
      - "50000-50100:50000-50100/udp"
    networks:
      - voxpilot
EOF
)"
    AGENT_LIVEKIT_DEPENDS="$(cat <<'EOF'
      - livekit
EOF
)"
  else
    LIVEKIT_SERVICE_BLOCK="# LiveKit Cloud mode — no local SFU service"
    AGENT_LIVEKIT_DEPENDS=""
  fi
  export LIVEKIT_SERVICE_BLOCK AGENT_LIVEKIT_DEPENDS
}

setup_host_postgres_redis() {
  [[ "${SETUP_HOST_SERVICES}" == "y" ]] || {
    warn "Skipping host Postgres/Redis install — ensure they already listen for Docker clients."
    return 0
  }
  if [[ "$(id -u)" -ne 0 ]]; then
    err "Host Postgres/Redis setup needs root (sudo)."
    exit 1
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    err "apt-get required for automatic Postgres/Redis install"
    exit 1
  fi

  if [[ ! "${PG_USER}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ || ! "${PG_DB}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    err "PG_USER / PG_DB must be simple identifiers (letters, numbers, underscore)"
    exit 1
  fi

  info "Installing PostgreSQL + Redis on host..."
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql postgresql-contrib redis-server

  systemctl enable --now postgresql redis-server

  # Postgres: listen on all interfaces (firewall should not expose 5432 publicly)
  local pg_conf
  pg_conf="$(sudo -u postgres psql -tA -c "SHOW config_file;" | tr -d '[:space:]')"
  if [[ -n "${pg_conf}" && -f "${pg_conf}" ]]; then
    if grep -qE "^[# ]*listen_addresses" "${pg_conf}"; then
      sed -i "s/^[# ]*listen_addresses.*/listen_addresses = '*'/" "${pg_conf}"
    else
      echo "listen_addresses = '*'" >> "${pg_conf}"
    fi
  fi

  local hba
  hba="$(sudo -u postgres psql -tA -c "SHOW hba_file;" | tr -d '[:space:]')"
  if [[ -n "${hba}" && -f "${hba}" ]]; then
    if ! grep -q "callandflow-docker" "${hba}"; then
      cat >> "${hba}" <<EOF

# callandflow-docker — allow Docker bridge / private ranges
host    ${PG_DB}    ${PG_USER}    172.16.0.0/12    scram-sha-256
host    ${PG_DB}    ${PG_USER}    192.168.0.0/16   scram-sha-256
host    ${PG_DB}    ${PG_USER}    10.0.0.0/8       scram-sha-256
EOF
    fi
  fi

  local pg_pass_sql
  pg_pass_sql="$(python3 -c 'import sys; print(sys.argv[1].replace("'"'"'", "''"))' "${PG_PASSWORD}")"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${PG_USER}') THEN
    CREATE ROLE ${PG_USER} LOGIN PASSWORD '${pg_pass_sql}';
  ELSE
    ALTER ROLE ${PG_USER} WITH LOGIN PASSWORD '${pg_pass_sql}';
  END IF;
END
\$\$;
SQL
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1; then
    sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER}"
  fi
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "GRANT ALL PRIVILEGES ON DATABASE ${PG_DB} TO ${PG_USER}"

  systemctl restart postgresql

  # Redis: listen broadly but password-protected — do NOT open 6379 on public firewall
  local redis_conf="/etc/redis/redis.conf"
  if [[ ! -f "${redis_conf}" ]]; then
    redis_conf="/etc/redis.conf"
  fi
  if [[ -f "${redis_conf}" ]]; then
    if grep -qE "^bind " "${redis_conf}"; then
      sed -i 's/^bind .*/bind 0.0.0.0 ::/' "${redis_conf}"
    else
      echo "bind 0.0.0.0 ::" >> "${redis_conf}"
    fi
    python3 - "${redis_conf}" "${REDIS_PASSWORD}" <<'PY'
import pathlib, re, sys
path, password = pathlib.Path(sys.argv[1]), sys.argv[2]
text = path.read_text(encoding="utf-8")
line = f"requirepass {password}"
if re.search(r"^#?\s*requirepass\s+.*$", text, flags=re.M):
    text = re.sub(r"^#?\s*requirepass\s+.*$", line, text, count=1, flags=re.M)
else:
    text += "\n" + line + "\n"
path.write_text(text, encoding="utf-8")
PY
    sed -i 's/^supervised no/supervised systemd/' "${redis_conf}" || true
  fi
  systemctl restart redis-server

  # Persist host credentials for ops (chmod 600) — not the container URLs
  write_file "${OUT_DIR}/host-data.env" 600 <<EOF
# Host Postgres / Redis (generated by deploy/install.sh)
PG_HOST=127.0.0.1
PG_PORT=${PG_PORT}
PG_DB=${PG_DB}
PG_USER=${PG_USER}
PG_PASSWORD=${PG_PASSWORD}
REDIS_HOST=127.0.0.1
REDIS_PORT=${REDIS_PORT}
REDIS_PASSWORD=${REDIS_PASSWORD}
# From Docker containers use:
#   ${DATABASE_URL}
#   ${REDIS_URL}
EOF

  ok "Host PostgreSQL + Redis configured"
  warn "Do not expose ports ${PG_PORT}/${REDIS_PORT} on the public firewall."
}

write_env_files() {
  info "Writing environment files..."

  write_file "${REPO_ROOT}/platform/.env.production" 600 <<EOF
# Generated by deploy/install.sh — do not commit

ENVIRONMENT=production
COOKIE_SECURE=true
ALLOW_ENV_TENANT_FALLBACK=false

DATABASE_URL=${DATABASE_URL}
PLATFORM_API_HOST=0.0.0.0
PLATFORM_API_PORT=8000

LIVEKIT_URL=${LIVEKIT_URL}
LIVEKIT_API_KEY=${LIVEKIT_API_KEY}
LIVEKIT_API_SECRET=${LIVEKIT_API_SECRET}
LIVEKIT_SIP_HOST=${LIVEKIT_SIP_HOST}
AGENT_NAME=${AGENT_NAME}

TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}

CREDENTIALS_ENCRYPTION_KEY=${CREDENTIALS_ENCRYPTION_KEY}
METADATA_HMAC_SECRET=${METADATA_HMAC_SECRET}
INTERNAL_SERVICE_TOKEN=${INTERNAL_SERVICE_TOKEN}
SESSION_SECRET=${SESSION_SECRET}

OPS_CORS_ORIGINS=https://${WEB_DOMAIN},https://www.${WEB_DOMAIN}

STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
STRIPE_CHECKOUT_SUCCESS_URL=https://${WEB_DOMAIN}/settings/billing?checkout=success
STRIPE_CHECKOUT_CANCEL_URL=https://${WEB_DOMAIN}/signup?canceled=1
STRIPE_PORTAL_RETURN_URL=https://${WEB_DOMAIN}/settings/billing
EOF

  write_file "${REPO_ROOT}/web/.env.production" 600 <<EOF
# Generated by deploy/install.sh — do not commit

NEXT_PUBLIC_SITE_URL=https://${WEB_DOMAIN}
NEXT_PUBLIC_PLATFORM_API_URL=https://${API_DOMAIN}

LIVEKIT_URL=${LIVEKIT_URL}
LIVEKIT_API_KEY=${LIVEKIT_API_KEY}
LIVEKIT_API_SECRET=${LIVEKIT_API_SECRET}
AGENT_NAME=${AGENT_NAME}
METADATA_HMAC_SECRET=${METADATA_HMAC_SECRET}
EOF

  write_file "${REPO_ROOT}/voice-agent/.env.production" 600 <<EOF
# Generated by deploy/install.sh — do not commit
# Self-host / server worker: LIVEKIT_* required.
# (LiveKit Cloud managed agents inject LIVEKIT_* themselves — not this path.)

LIVEKIT_URL=${LIVEKIT_URL}
LIVEKIT_API_KEY=${LIVEKIT_API_KEY}
LIVEKIT_API_SECRET=${LIVEKIT_API_SECRET}
OPENAI_API_KEY=${OPENAI_API_KEY}
PLATFORM_API_URL=https://${API_DOMAIN}
INTERNAL_SERVICE_TOKEN=${INTERNAL_SERVICE_TOKEN}
METADATA_HMAC_SECRET=${METADATA_HMAC_SECRET}
ALLOW_ENV_TENANT_FALLBACK=false
VOICE_RUNTIME_MODE=production
AGENT_NAME=${AGENT_NAME}
AGENT_LANGUAGE=en
OPENAI_REALTIME_MODEL=gpt-realtime
OPENAI_VOICE=marin
OPENAI_TEMPERATURE=0.8
USER_AWAY_TIMEOUT_SEC=15
MAX_CALL_DURATION_SEC=900
INACTIVITY_CHECK_LIMIT=2
INACTIVITY_CHECK_INTERVAL_SEC=10
MAX_SPOKEN_SENTENCES=2
AGENT_PROFILE_TIMEOUT_SEC=5
AGENT_PROFILE_CACHE_TTL_SEC=60
REDIS_URL=${REDIS_URL}
EOF

  ok "  platform/.env.production"
  ok "  web/.env.production"
  ok "  voice-agent/.env.production"
}

write_nginx_and_compose() {
  info "Rendering nginx + compose templates..."
  ensure_dirs
  export_template_vars

  render_tpl "${TEMPLATES}/nginx-web.conf.tpl" "${OUT_DIR}/nginx/${WEB_DOMAIN}.conf"
  render_tpl "${TEMPLATES}/nginx-api.conf.tpl" "${OUT_DIR}/nginx/${API_DOMAIN}.conf"
  if [[ "${LIVEKIT_MODE}" == "selfhost" ]]; then
    render_tpl "${TEMPLATES}/nginx-livekit.conf.tpl" "${OUT_DIR}/nginx/${LIVEKIT_DOMAIN}.conf"
    render_tpl "${TEMPLATES}/livekit.yaml.tpl" "${OUT_DIR}/livekit/livekit.yaml"
    chmod 600 "${OUT_DIR}/livekit/livekit.yaml"
  fi

  # Compose template has multiline blocks — write via python with env
  COMPOSE_TPL="${TEMPLATES}/docker-compose.selfhost.yml.tpl" \
  COMPOSE_DEST="${COMPOSE_OUT}" \
  python3 <<'PY'
import os
from pathlib import Path

src = Path(os.environ["COMPOSE_TPL"])
dest = Path(os.environ["COMPOSE_DEST"])
text = src.read_text(encoding="utf-8")
for key in (
    "WEB_DOMAIN",
    "API_DOMAIN",
    "LIVEKIT_MODE",
    "LIVEKIT_SERVICE_BLOCK",
    "AGENT_LIVEKIT_DEPENDS",
):
    text = text.replace("${" + key + "}", os.environ[key])
dest.write_text(text, encoding="utf-8")
print(f"wrote {dest}")
PY

  ok "  ${OUT_DIR}/nginx/"
  ok "  ${COMPOSE_OUT}"
  [[ "${LIVEKIT_MODE}" == "selfhost" ]] && ok "  ${OUT_DIR}/livekit/livekit.yaml"
}

install_nginx_sites() {
  [[ "${INSTALL_NGINX}" == "y" ]] || return 0
  if [[ "$(id -u)" -ne 0 ]]; then
    warn "Not root — skipping nginx install. Copy configs later from ${OUT_DIR}/nginx/"
    return 0
  fi
  if ! command -v nginx >/dev/null 2>&1; then
    info "Installing nginx..."
    if command -v apt-get >/dev/null 2>&1; then
      apt-get update -qq
      DEBIAN_FRONTEND=noninteractive apt-get install -y nginx
    else
      err "apt-get not found; install nginx manually"
      return 1
    fi
  fi
  mkdir -p /var/www/certbot /etc/nginx/sites-available /etc/nginx/sites-enabled

  # Bootstrap HTTP-only configs for certbot first if certs missing
  for domain_file in "${OUT_DIR}/nginx/"*.conf; do
    base="$(basename "${domain_file}")"
    domain="${base%.conf}"
    server_names="${domain}"
    if [[ "${domain}" == "${WEB_DOMAIN}" ]]; then
      server_names="${WEB_DOMAIN} www.${WEB_DOMAIN}"
    fi
    if [[ ! -f "/etc/letsencrypt/live/${domain}/fullchain.pem" ]]; then
      write_file "/etc/nginx/sites-available/${base}" 644 <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${server_names};
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 'callandflow-bootstrap'; add_header Content-Type text/plain; }
}
EOF
    else
      cp "${domain_file}" "/etc/nginx/sites-available/${base}"
    fi
    ln -sfn "/etc/nginx/sites-available/${base}" "/etc/nginx/sites-enabled/${base}"
  done

  # Remove default site if present
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
  ok "Nginx sites installed (HTTP bootstrap or full TLS)"
}

issue_certs() {
  [[ "${INSTALL_CERTBOT}" == "y" ]] || return 0
  if [[ "$(id -u)" -ne 0 ]]; then
    warn "Not root — skipping certbot"
    return 0
  fi
  if ! command -v certbot >/dev/null 2>&1; then
    info "Installing certbot..."
    if command -v apt-get >/dev/null 2>&1; then
      DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx
    else
      err "Install certbot manually"
      return 1
    fi
  fi

  local domains=("${WEB_DOMAIN}" "${API_DOMAIN}")
  [[ "${LIVEKIT_MODE}" == "selfhost" ]] && domains+=("${LIVEKIT_DOMAIN}")

  for d in "${domains[@]}"; do
    info "Certbot: ${d}"
    local cert_args=(-d "${d}")
    # Cover www on the apex web cert
    if [[ "${d}" == "${WEB_DOMAIN}" ]]; then
      cert_args+=(-d "www.${WEB_DOMAIN}")
    fi
    certbot certonly --webroot -w /var/www/certbot \
      "${cert_args[@]}" \
      --email "${CERTBOT_EMAIL}" \
      --agree-tos \
      --non-interactive \
      --keep-until-expiring || {
        warn "Certbot failed for ${d}. Check DNS A record → this server, ports 80/443 open."
        continue
      }
    # Install full TLS nginx config now that cert exists
    if [[ -f "${OUT_DIR}/nginx/${d}.conf" ]]; then
      cp "${OUT_DIR}/nginx/${d}.conf" "/etc/nginx/sites-available/${d}.conf"
      ln -sfn "/etc/nginx/sites-available/${d}.conf" "/etc/nginx/sites-enabled/${d}.conf"
    fi
  done

  # Ensure ssl snippets exist
  if [[ ! -f /etc/letsencrypt/options-ssl-nginx.conf ]]; then
    warn "Missing /etc/letsencrypt/options-ssl-nginx.conf — installing certbot nginx plugin usually creates it."
  fi
  if [[ ! -f /etc/letsencrypt/ssl-dhparams.pem ]]; then
    openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048 || true
  fi

  nginx -t && systemctl reload nginx
  ok "TLS certificates processed"
}

start_stack() {
  [[ "${START_STACK}" == "y" ]] || return 0
  info "Building and starting stack (docker compose)..."
  cd "${REPO_ROOT}"
  export COMPOSE_BAKE=false
  if [[ "${LIVEKIT_MODE}" == "selfhost" ]]; then
    docker compose -f docker-compose.selfhost.yml pull livekit || true
  fi
  docker compose -f docker-compose.selfhost.yml up -d --build
  ok "Stack started"
  docker compose -f docker-compose.selfhost.yml ps
}

print_firewall() {
  [[ "${OPEN_FIREWALL}" == "y" ]] || return 0
  cat <<EOF

${YELLOW}Firewall ports to open:${NC}
  80/tcp, 443/tcp          — nginx / certbot
  8000/tcp, 3000/tcp       — optional (prefer nginx only)
EOF
  if [[ "${LIVEKIT_MODE}" == "selfhost" ]]; then
    cat <<EOF
  7880/tcp                 — LiveKit (proxied via nginx; can stay local)
  7881/tcp                 — LiveKit WebRTC TCP  ${RED}PUBLIC${NC}
  50000:50100/udp          — LiveKit WebRTC UDP ${RED}PUBLIC${NC}
EOF
  fi
  cat <<EOF

Example (ufw):
  ufw allow 80/tcp
  ufw allow 443/tcp
EOF
  if [[ "${LIVEKIT_MODE}" == "selfhost" ]]; then
    cat <<EOF
  ufw allow 7881/tcp
  ufw allow 50000:50100/udp
EOF
  fi
}

print_summary() {
  cat <<EOF

${GREEN}═══ Done ═══${NC}

Domains
  Web:     https://${WEB_DOMAIN}  (www → apex redirect)
  API:     https://${API_DOMAIN}
  LiveKit: ${LIVEKIT_URL}  (${LIVEKIT_MODE})

Host data (not Docker)
  Postgres: 127.0.0.1:${PG_PORT}/${PG_DB} (user ${PG_USER})
  Redis:    127.0.0.1:${REDIS_PORT}
  From containers: host.docker.internal
  Creds file: deploy/generated/host-data.env

Files
  platform/.env.production
  web/.env.production
  voice-agent/.env.production
  docker-compose.selfhost.yml
  deploy/generated/nginx/
  deploy/answers.env          (non-secret re-run defaults)

Useful commands
  docker compose -f docker-compose.selfhost.yml ps
  docker compose -f docker-compose.selfhost.yml logs -f platform
  docker compose -f docker-compose.selfhost.yml logs -f voice-agent
  curl -s https://${API_DOMAIN}/health

Stripe webhook
  https://${API_DOMAIN}/billing/webhooks/stripe

Notes
  • DNS A records for all domains must point to this server before certbot.
  • Do not commit .env.production files.
  • If using LiveKit Cloud managed agents, do NOT also run voice-agent here
    with the same AGENT_NAME (pick one).
  • Self-host SIP is separate — set LIVEKIT_SIP_HOST after you deploy livekit-sip.

EOF
}

main() {
  cd "${REPO_ROOT}"
  banner
  check_prereqs
  load_answers_if_any
  collect_inputs
  write_env_files
  write_nginx_and_compose
  save_answers
  setup_host_postgres_redis
  install_nginx_sites
  issue_certs
  start_stack
  print_firewall
  print_summary
}

main "$@"
