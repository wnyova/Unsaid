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
- SQLite locally, PostgreSQL in production

## Local
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app app run --debug
```

## Spotify
Create an app in the Spotify Developer Dashboard. Put its Client ID and Client Secret in `.env`. Unsaid uses Spotify Client Credentials for track search.

## Ubuntu VPS: Gunicorn + Nginx + PostgreSQL
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx postgresql postgresql-contrib git
sudo mkdir -p /opt/unsaid
sudo chown $USER:$USER /opt/unsaid
git clone git@github.com:wnyova/Unsaid.git /opt/unsaid
cd /opt/unsaid
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo -u postgres psql
```
Then in PostgreSQL:
```sql
CREATE USER unsaid WITH PASSWORD 'CHANGE_THIS_PASSWORD';
CREATE DATABASE unsaid OWNER unsaid;
\q
```
Configure:
```bash
cp .env.example .env
nano .env
```
Production example:
```env
SECRET_KEY=generate-a-long-random-secret
DATABASE_URL=postgresql+psycopg://unsaid:CHANGE_THIS_PASSWORD@127.0.0.1/unsaid
BASE_URL=https://your-domain.example
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```
Generate a secret:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Create `/etc/systemd/system/unsaid.service`:
```ini
[Unit]
Description=Unsaid web app
After=network.target postgresql.service
[Service]
User=YOUR_LINUX_USER
Group=www-data
WorkingDirectory=/opt/unsaid
EnvironmentFile=/opt/unsaid/.env
ExecStart=/opt/unsaid/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 app:app
Restart=on-failure
PrivateTmp=true
[Install]
WantedBy=multi-user.target
```
Enable it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now unsaid
```

Nginx `/etc/nginx/sites-available/unsaid`:
```nginx
server {
 listen 80;
 server_name your-domain.example;
 client_max_body_size 1m;
 location / {
  proxy_pass http://127.0.0.1:8000;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
 }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/unsaid /etc/nginx/sites-enabled/unsaid
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example
```

Update later:
```bash
cd /opt/unsaid
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart unsaid
```

Before large public use, add Redis-backed rate limiting, CSRF protection, report/moderation controls, privacy/terms pages, deliberate proxy log retention, and CAPTCHA/Turnstile.

## License
MIT