# Self-hosted LiveKit — ${LIVEKIT_DOMAIN} -> 127.0.0.1:7880 (WSS)
# RTC UDP/TCP ports are exposed directly by Docker (not via nginx).
# Managed by deploy/install.sh

upstream callandflow_livekit {
    server 127.0.0.1:7880;
    keepalive 64;
}

map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    listen [::]:80;
    server_name ${LIVEKIT_DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${LIVEKIT_DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${LIVEKIT_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${LIVEKIT_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://callandflow_livekit;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }
}
