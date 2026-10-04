# Call & Flow production installer

Interactive script that asks for domains and secrets, then writes:

- `platform/.env.production`
- `web/.env.production`
- `voice-agent/.env.production`
- `docker-compose.selfhost.yml` (**no** Postgres/Redis containers)
- `deploy/generated/nginx/*.conf`
- optional self-hosted `deploy/generated/livekit/livekit.yaml`
- optional host PostgreSQL + Redis (systemd)
- optional nginx + Let's Encrypt + `docker compose up`

## Architecture

| Service | Where it runs |
|---|---|
| PostgreSQL | **Host** (systemd) |
| Redis | **Host** (systemd) |
| Platform / Web / Agent | Docker |
| LiveKit SFU (optional) | Docker (uses host Redis) |
| Nginx + TLS | Host |

Docker containers reach host DB/Redis via `host.docker.internal` (`extra_hosts: host-gateway`).

## Quick start (on the server)

```bash
cd /path/to/call-bot
git pull

# DNS A records first:
#   callandflow.com
#   www.callandflow.com
#   api.callandflow.com
#   livekit.callandflow.com   (only if self-hosting LiveKit)

cp deploy/answers.example.env deploy/answers.env
sudo bash deploy/install.sh
```

Installer will:

1. Prompt for Postgres/Redis credentials (or auto-generate passwords)
2. `apt install` + configure PostgreSQL/Redis on the host (if you say yes)
3. Write env files using `host.docker.internal`
4. Install nginx/certs and start app containers

## Firewall

**Open publicly:** `80`, `443` (and LiveKit `7881` + UDP `50000-50100` if self-hosting SFU)

**Do not open publicly:** `5432` (Postgres), `6379` (Redis)

**Required for host DB/Redis:** allow Docker private ranges → host ports (UFW often blocks this and causes `connection timeout expired` in the platform container):

```bash
ufw allow from 172.16.0.0/12 to any port 5432 proto tcp
ufw allow from 172.16.0.0/12 to any port 6379 proto tcp
ufw reload
```

## What it asks

| Prompt | Purpose |
|---|---|
| Web / API domains | Public HTTPS hosts |
| LiveKit mode | Cloud **or** self-host SFU |
| Setup host Postgres/Redis | Install on machine (not Docker) |
| PG/Redis user + ports | Host data services |
| Shared secrets / OpenAI / Stripe | App secrets |
| Nginx / Certbot / Start | TLS + bring stack up |

## After install

```bash
sudo systemctl status postgresql redis-server
docker compose -f docker-compose.selfhost.yml ps
docker compose -f docker-compose.selfhost.yml logs -f platform
curl -s https://api.callandflow.com/health
```

Host credentials (for debugging on the server): `deploy/generated/host-data.env`

### LiveKit Redis `NOAUTH`

Self-host LiveKit needs the Redis password in `deploy/generated/livekit/livekit.yaml` (not only in `REDIS_URL`). `NOAUTH` means LiveKit sent no password; `WRONGPASS` means a mismatch with Redis `requirepass`.

```bash
cd /opt/callandflow/call-bot
set -a && source deploy/generated/host-data.env && set +a

# 1) Confirm host Redis accepts this password
redis-cli -h 127.0.0.1 -p "${REDIS_PORT:-6379}" -a "${REDIS_PASSWORD}" ping

# 2) Rewrite the redis: block (address + password)
python3 - <<'PY'
import os, pathlib, re
p = pathlib.Path("deploy/generated/livekit/livekit.yaml")
text = p.read_text(encoding="utf-8")
pw = os.environ["REDIS_PASSWORD"]
port = os.environ.get("REDIS_PORT", "6379")
host = os.environ.get("REDIS_HOST_FOR_CONTAINERS", "host.docker.internal")
if not pw:
    raise SystemExit("REDIS_PASSWORD empty in host-data.env")
# YAML double-quoted scalar
esc = pw.replace("\\", "\\\\").replace('"', '\\"')
block = (
    "redis:\n"
    f"  address: {host}:{port}\n"
    f'  password: "{esc}"\n'
)
if re.search(r"(?m)^redis:\s*$", text):
    text = re.sub(
        r"(?m)^redis:\s*\n(?:[ \t]+.*\n)*",
        block,
        text,
        count=1,
    )
else:
    text = block + "\n" + text
p.write_text(text, encoding="utf-8")
# Show structure without leaking the secret
for line in p.read_text(encoding="utf-8").splitlines():
    if "password:" in line:
        print(re.sub(r'password:\s*".*"', f'password: "***{len(pw)} chars***"', line))
    elif line.strip().startswith("redis:") or "address:" in line:
        print(line)
print("host-data REDIS_PASSWORD length:", len(pw))
PY
chmod 600 deploy/generated/livekit/livekit.yaml

# 3) Confirm the container mount sees the same file
docker compose -f docker-compose.selfhost.yml run --rm --no-deps --entrypoint cat livekit /etc/livekit.yaml | sed -E 's/(password: ).*/\1***redacted***/'

# 4) Recreate (bind-mount change + clean process)
docker compose -f docker-compose.selfhost.yml up -d --force-recreate livekit
sleep 3
docker compose -f docker-compose.selfhost.yml logs livekit --since 2m
docker compose -f docker-compose.selfhost.yml ps livekit
```

Stripe webhook: `https://api.callandflow.com/billing/webhooks/stripe`

### Agent cannot connect to `livekit.*.com:443`

SFU on `:7880` can be healthy while the agent still fails if nginx + Let's Encrypt for the LiveKit domain are missing. Agent uses `LIVEKIT_URL=wss://livekit...` (port 443), not `:7880` directly.

```bash
# DNS + local SFU
getent hosts livekit.callandflow.com
curl -sS http://127.0.0.1:7880

# nginx site + cert
ls -la /etc/nginx/sites-enabled/ | grep -i livekit || true
ls -la /etc/letsencrypt/live/livekit.callandflow.com/ 2>/dev/null || true
ss -lntp | grep -E ':80|:443'

# Install/enable LiveKit nginx + cert (domain must already resolve here)
DOMAIN=livekit.callandflow.com
EMAIL=admin@callandflow.com   # change if needed
mkdir -p /var/www/certbot
cp "deploy/generated/nginx/${DOMAIN}.conf" "/etc/nginx/sites-available/${DOMAIN}.conf" 2>/dev/null || true
# HTTP-only bootstrap if full TLS config would fail without certs yet:
if [[ ! -f /etc/letsencrypt/live/${DOMAIN}/fullchain.pem ]]; then
  cat > "/etc/nginx/sites-available/${DOMAIN}.conf" <<EOF
server {
  listen 80;
  listen [::]:80;
  server_name ${DOMAIN};
  location /.well-known/acme-challenge/ { root /var/www/certbot; }
  location / { return 200 'livekit-acme-ok'; add_header Content-Type text/plain; }
}
EOF
fi
ln -sfn "/etc/nginx/sites-available/${DOMAIN}.conf" "/etc/nginx/sites-enabled/${DOMAIN}.conf"
nginx -t && systemctl reload nginx
certbot certonly --webroot -w /var/www/certbot -d "${DOMAIN}" --email "${EMAIL}" --agree-tos --non-interactive
cp "deploy/generated/nginx/${DOMAIN}.conf" "/etc/nginx/sites-available/${DOMAIN}.conf"
ln -sfn "/etc/nginx/sites-available/${DOMAIN}.conf" "/etc/nginx/sites-enabled/${DOMAIN}.conf"
nginx -t && systemctl reload nginx

# Verify WSS path, then restart agent
curl -sSI https://${DOMAIN}/ | head -n 20
ufw allow 80/tcp; ufw allow 443/tcp
ufw allow 7881/tcp; ufw allow 50000:50100/udp
docker compose -f docker-compose.selfhost.yml up -d --force-recreate voice-agent
docker compose -f docker-compose.selfhost.yml logs voice-agent --tail 30
```

## Re-run

Non-secret answers → `deploy/answers.env`.  
Passwords stay in `.env.production` + `deploy/generated/host-data.env` (`chmod 600`).

## Manual host services

If you skip auto-setup, install Postgres/Redis yourself, then point containers at:

```text
DATABASE_URL=postgresql+psycopg://USER:PASS@host.docker.internal:5432/call_bot
REDIS_URL=redis://:PASS@host.docker.internal:6379/0
```

Postgres must allow Docker bridge CIDRs in `pg_hba.conf`. Redis must listen beyond `127.0.0.1` (password required).
