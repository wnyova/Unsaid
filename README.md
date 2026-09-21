# Unsaid

**Things you never got to say.**

Self-hosted anonymous-letter platform with optional Spotify tracks.

## Features
- Personal `/to/username` pages
- Anonymous sending without sender accounts
- Private recipient inbox
- Publish/unpublish selected letters
- Spotify track search and attachment
- Basic rate limiting + honeypot
- MariaDB/MySQL production database
- Gunicorn on port 8001 so it can coexist with another app on port 8000

## Ubuntu VPS deployment (existing MariaDB)

Clone into `/opt/unsaid`:

```bash
cd /opt
sudo git clone https://github.com/wnyova/Unsaid.git unsaid
sudo chown -R $USER:$USER /opt/unsaid
cd /opt/unsaid
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### MariaDB

Use the existing MariaDB service, but create a separate database and account:

```bash
sudo mariadb
```

```sql
CREATE DATABASE unsaid CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'unsaid'@'localhost' IDENTIFIED BY 'CHANGE_THIS_PASSWORD';
GRANT ALL PRIVILEGES ON unsaid.* TO 'unsaid'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Test it:

```bash
mariadb -u unsaid -p unsaid
```

### Environment

```bash
cd /opt/unsaid
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"
nano .env
```

Example:

```env
SECRET_KEY=YOUR_GENERATED_SECRET
DATABASE_URL=mysql+pymysql://unsaid:CHANGE_THIS_PASSWORD@127.0.0.1:3306/unsaid?charset=utf8mb4
BASE_URL=http://192.168.0.139:8001
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

If the database password contains URL-reserved characters, URL-encode it or use a long alphanumeric password.

Initialize tables:

```bash
cd /opt/unsaid
source .venv/bin/activate
python -c "from app import app; print('Unsaid database initialized')"
mariadb -u unsaid -p unsaid -e "SHOW TABLES;"
```

### Test on LAN

```bash
cd /opt/unsaid
source .venv/bin/activate
gunicorn --workers 2 --bind 0.0.0.0:8001 app:app
```

Open `http://192.168.0.139:8001`. This does not use or modify port 8000.

### systemd

Create `/etc/systemd/system/unsaid.service`:

```ini
[Unit]
Description=Unsaid web app
After=network.target mariadb.service

[Service]
User=YOUR_LINUX_USER
Group=www-data
WorkingDirectory=/opt/unsaid
EnvironmentFile=/opt/unsaid/.env
ExecStart=/opt/unsaid/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8001 app:app
Restart=on-failure
RestartSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now unsaid
sudo systemctl status unsaid
```

For direct LAN access instead, bind to `0.0.0.0:8001`; for a public deployment behind Nginx, keep `127.0.0.1:8001`.

### Nginx

Create `/etc/nginx/sites-available/unsaid`:

```nginx
server {
    listen 80;
    server_name your-domain.example;

    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/unsaid /etc/nginx/sites-enabled/unsaid
sudo nginx -t
sudo systemctl reload nginx
```

For HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example
```

Then change `BASE_URL` in `.env` to the final HTTPS URL and restart:

```bash
sudo systemctl restart unsaid
```

## Spotify

Create an app in the Spotify Developer Dashboard and place its Client ID and Client Secret in `.env`. Unsaid uses Spotify Client Credentials for track search; senders do not need to log into Spotify.

## Updating later

```bash
cd /opt/unsaid
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart unsaid
```

## Production note

Before broad public use, add persistent/Redis-backed rate limiting, CSRF protection, report/moderation controls, privacy/terms pages, CAPTCHA/Turnstile, and a deliberate proxy-log retention policy.

## License
MIT