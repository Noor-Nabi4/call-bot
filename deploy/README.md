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

Stripe webhook: `https://api.callandflow.com/billing/webhooks/stripe`

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
