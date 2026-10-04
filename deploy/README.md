# VoxPilot production installer

Interactive script that asks for domains and secrets, then writes:

- `platform/.env.production`
- `web/.env.production`
- `voice-agent/.env.production`
- `docker-compose.selfhost.yml`
- `deploy/generated/nginx/*.conf`
- optional self-hosted `deploy/generated/livekit/livekit.yaml`
- optional nginx install + Let's Encrypt + `docker compose up`

## Quick start (on the server)

```bash
cd /path/to/call-bot
git pull

# DNS A records first (Call & Flow):
#   callandflow.com
#   www.callandflow.com
#   api.callandflow.com
#   livekit.callandflow.com   (only if self-hosting LiveKit)

cp deploy/answers.example.env deploy/answers.env   # optional defaults
sudo bash deploy/install.sh
```

Run as root if you want nginx + certbot installed automatically. Without root, configs are still generated under `deploy/generated/`.

## What it asks

| Prompt | Purpose |
|---|---|
| Web / API domains | Public HTTPS hosts |
| LiveKit mode | Cloud **or** self-host SFU on this machine |
| LiveKit URL / keys | Cloud keys, or auto-generated for self-host |
| `DATABASE_URL` | Postgres (not `localhost` inside Docker) |
| Shared secrets | Auto-generated if left blank |
| `OPENAI_API_KEY` | Voice agent |
| Stripe keys | Required (platform fail-closed) |
| Twilio | Optional |
| Nginx / Certbot / Start | Install TLS + bring stack up |

## After install

```bash
docker compose -f docker-compose.selfhost.yml ps
docker compose -f docker-compose.selfhost.yml logs -f platform
curl -s https://API_DOMAIN/health
```

Stripe webhook:

```text
https://API_DOMAIN/billing/webhooks/stripe
```

## Re-run

Non-secret answers are saved to `deploy/answers.env`. Secrets are **not** saved there — they stay in `.env.production` files (`chmod 600`).

```bash
sudo bash deploy/install.sh
```

## Modes

### LiveKit Cloud

- Local services: redis, platform, web, voice-agent
- Set Cloud `LIVEKIT_URL` / key / secret
- Do **not** also run a Cloud-managed agent with the same `AGENT_NAME`

### Self-host LiveKit

- Adds `livekit/livekit-server` + local keys in `deploy/generated/livekit/livekit.yaml`
- Nginx terminates TLS for `wss://LIVEKIT_DOMAIN`
- Open `7881/tcp` and `50000-50100/udp` on the firewall
- SIP is **not** installed by this script (separate LiveKit SIP server later)

## Security

- Never commit `.env.production` or `deploy/generated/livekit/livekit.yaml`
- Prefer exposing only `80/443` publicly; keep `:3000` / `:8000` local if possible
- Rotate secrets by re-running the script (or editing env files) and restarting compose

## Manual nginx copy

If you skipped auto-install:

```bash
sudo cp deploy/generated/nginx/*.conf /etc/nginx/sites-available/
sudo ln -sfn /etc/nginx/sites-available/WEB.conf /etc/nginx/sites-enabled/
# certbot, then copy full TLS configs again after certs exist
sudo nginx -t && sudo systemctl reload nginx
```
