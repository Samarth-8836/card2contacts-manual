# Quick Production Deployment Summary

## What Was Created

**Docker Files:**
- `Dockerfile` - Backend container (FastAPI)
- `Dockerfile.frontend` - Frontend container (Nginx)
- `nginx-production.conf` - Nginx config with SSL
- `docker-compose.production.yml` - Production orchestration
- `.dockerignore` - Build exclusions

**Configuration Files:**
- `.env.production` - Production environment template
- `.env.production.local` - Your actual secrets (create this, don't commit)
- `frontend/config.js` - Updated with production URLs

**Documentation:**
- `UBUNTU_DEPLOYMENT_GUIDE.md` - Complete step-by-step guide
- `PRODUCTION_CHANGES_CHECKLIST.md` - All changes needed
- `DOCKER_DEPLOYMENT.md` - General Docker guide

## Deployment URLs

- **Main App:** https://app.card2contacts.com
- **Admin Panel:** https://app.card2contacts.com/admin.html
- **API Docs:** https://app.card2contacts.com/api/docs

## Quick Deploy (5 Steps)

### 1. On Ubuntu Server:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Clone and Setup:
```bash
cd /opt
sudo mkdir -p digicard
sudo chown $USER:$USER digicard
cd digicard
git clone <your-repo-url> .
```

### 3. Get SSL Certificate:
```bash
sudo apt install certbot
sudo certbot certonly --standalone -d app.card2contacts.com
sudo mkdir -p certs
sudo cp /etc/letsencrypt/live/app.card2contacts.com/fullchain.pem certs/
sudo cp /etc/letsencrypt/live/app.card2contacts.com/privkey.pem certs/
sudo chown $USER:$USER certs/*
```

### 4. Configure Environment:
```bash
cp .env.production .env.production.local
nano .env.production.local
```

**Critical to update:**
- `POSTGRES_PASSWORD` (generate: `openssl rand -base64 32`)
- `SECRET_KEY` (generate: `openssl rand -hex 32`)
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- `GROQ_API_KEY` and `MISTRAL_API_KEY`
- SMTP credentials

### 5. Deploy:
```bash
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d
docker-compose -f docker-compose.production.yml exec backend python create_app_owner.py
```

## Production Changes Summary

**Updated from Development:**
- ✅ Domain: `https://192.168.29.234.sslip.io:8000` → `https://app.card2contacts.com`
- ✅ Environment: `development` → `production`
- ✅ Console logs: `enabled` → `disabled`
- ✅ Error reporting: `disabled` → `enabled`
- ✅ SSL: `none` → `full TLS/HTTPS`
- ✅ Database: `exposed` → `localhost only`
- ✅ CORS: `*` wildcard → `https://app.card2contacts.com`

**Key Features:**
- Frontend served on `/` → `index.html`
- Admin panel served on `/admin.html` → `admin.html`
- API proxied at `/api/` → backend container
- Automatic HTTPS redirect
- SSL auto-renewal
- Database backups
- Container auto-restart

## Important Files

**Don't Commit:**
- `.env.production.local` (contains secrets)
- `certs/` (SSL certificates)

**Don't Modify:**
- `.env.production` (template, use local copy instead)
- `backend/config.py` (defaults, use .env to override)

**Do Modify Before Deploy:**
- `docker-compose.production.yml` (update password references)
- `.env.production.local` (all your production values)

## Security Checklist

- [ ] Strong `POSTGRES_PASSWORD` generated
- [ ] Strong `SECRET_KEY` generated
- [ ] SSL certificates obtained
- [ ] Google OAuth configured for `app.card2contacts.com`
- [ ] API keys obtained (Groq, Mistral)
- [ ] Firewall configured (only 80, 443 open)
- [ ] Database port only on localhost
- [ ] `.env.production.local` not committed to git

## Common Commands

```bash
# Start services
docker-compose -f docker-compose.production.yml up -d

# Stop services
docker-compose -f docker-compose.production.yml down

# View logs
docker-compose -f docker-compose.production.yml logs -f

# Restart services
docker-compose -f docker-compose.production.yml restart

# Backup database
./backup.sh

# Update application
git pull && docker-compose -f docker-compose.production.yml up -d --build

# Check container status
docker-compose -f docker-compose.production.yml ps
```

## Troubleshooting

**Can't access SSL:**
```bash
sudo certbot renew --force-renewal
sudo cp /etc/letsencrypt/live/app.card2contacts.com/fullchain.pem certs/
sudo cp /etc/letsencrypt/live/app.card2contacts.com/privkey.pem certs/
docker-compose -f docker-compose.production.yml restart frontend
```

**Database connection failed:**
```bash
docker-compose -f docker-compose.production.yml exec db pg_isready -U admin
docker-compose -f docker-compose.production.yml logs db
```

**Container won't start:**
```bash
docker-compose -f docker-compose.production.yml logs
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

## Next Steps

1. Read `UBUNTU_DEPLOYMENT_GUIDE.md` for detailed instructions
2. Review `PRODUCTION_CHANGES_CHECKLIST.md` for all changes
3. Follow the 5-step quick deploy above
4. Verify deployment at https://app.card2contacts.com
