# ERA Competency - GCP VM Deployment Guide

This guide deploys the full Django app (frontend templates + backend + DB) on a single Ubuntu VM using Gunicorn + Nginx + systemd.

## 1) VM prerequisites

- Ubuntu 22.04+ VM on GCP
- Domain (optional but recommended)
- SSH access with sudo permissions

## 2) Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

## 3) Clone and prepare app

```bash
cd /var/www
sudo git clone <your-repo-url> era-competency
cd era-competency
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Environment variables

Create production env file:

```bash
touch .env
nano .env
```

Set at minimum:
- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- SMTP variables for OTP delivery

Optional but recommended:
- `DEFAULT_FROM_EMAIL`

## 5) Run migrations and collect static

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Create an admin user (for Django admin and admin portal access):

```bash
python manage.py createsuperuser
```

## 6) Create systemd service for Gunicorn

Create `/etc/systemd/system/era-competency.service`:

```ini
[Unit]
Description=ERA Competency Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/era-competency
EnvironmentFile=/var/www/era-competency/.env
ExecStart=/var/www/era-competency/.venv/bin/gunicorn core.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable era-competency
sudo systemctl start era-competency
sudo systemctl status era-competency
```

## 7) Configure Nginx reverse proxy

Create `/etc/nginx/sites-available/era-competency`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location /static/ {
        alias /var/www/era-competency/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/era-competency /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 8) Enable HTTPS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## 9) Firewall (GCP + UFW)

- Open ports `80` and `443` in GCP firewall rules.
- If UFW is enabled:

```bash
sudo ufw allow 'Nginx Full'
sudo ufw status
```

## 10) Post-deploy checks

- `systemctl status era-competency`
- `journalctl -u era-competency -f`
- OTP emails send successfully from login flow
- Admin portal works at `/portal/login/`
- Django admin works at `/admin/` (if needed)
- Static files load without 404s

## 11) Update workflow

```bash
cd /var/www/era-competency
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart era-competency
```
