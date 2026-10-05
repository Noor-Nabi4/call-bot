# Call & Flow web — ${WEB_DOMAIN} (+ www) -> 127.0.0.1:3000
# Managed by deploy/install.sh — do not hand-edit unless you know why.

upstream callandflow_web {
    server 127.0.0.1:3000;
    keepalive 32;
}

# Apex + ACME
server {
    listen 80;
    listen [::]:80;
    server_name ${WEB_DOMAIN} www.${WEB_DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://${WEB_DOMAIN}$request_uri;
    }
}

# www → canonical apex
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name www.${WEB_DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${WEB_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${WEB_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    return 301 https://${WEB_DOMAIN}$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${WEB_DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${WEB_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${WEB_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 20m;

    location / {
        proxy_pass http://callandflow_web;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
