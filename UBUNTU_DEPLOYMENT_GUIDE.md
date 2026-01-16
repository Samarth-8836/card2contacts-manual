# Production Deployment Guide - Ubuntu Server

This guide provides step-by-step instructions to deploy DigiCard Enterprise to an Ubuntu server.

## Prerequisites

- Ubuntu 20.04 LTS or 22.04 LTS
- Domain name pointing to your server (app.card2contacts.com)
- Root or sudo access
- At least 2GB RAM and 20GB disk space
- Valid SSL certificate for app.card2contacts.com

---

## Step 1: Server Initial Setup

### 1.1 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Required Packages

```bash
sudo apt install -y git curl wget python3-pip certbot
```

### 1.3 Create Application Directory

```bash
sudo mkdir -p /opt/digicard
sudo chown -R $USER:$USER /opt/digicard
cd /opt/digicard
```

---

## Step 2: Install Docker and Docker Compose

### 2.1 Install Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Activate group changes
newgrp docker
```

### 2.2 Install Docker Compose

```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker-compose --version
docker --version
```

---

## Step 3: Clone Repository

```bash
cd /opt/digicard
git clone <your-repo-url> .
```

---

## Step 4: Obtain SSL Certificate

### 4.1 Get SSL Certificate with Certbot

```bash
# Create directory for certificates
sudo mkdir -p /opt/digicard/certs

# Get certificate (standalone mode)
sudo certbot certonly --standalone -d app.card2contacts.com

# Copy certificates to application directory
sudo cp /etc/letsencrypt/live/app.card2contacts.com/fullchain.pem /opt/digicard/certs/
sudo cp /etc/letsencrypt/live/app.card2contacts.com/privkey.pem /opt/digicard/certs/

# Set permissions
sudo chown -R $USER:$USER /opt/digicard/certs/
sudo chmod 644 /opt/digicard/certs/*
```

### 4.3 Set Up Auto-Renewal

```bash
sudo crontab -e
```

Add this line at the end:

```
0 3 * * * certbot renew --quiet --post-hook "cp /etc/letsencrypt/live/app.card2contacts.com/fullchain.pem /opt/digicard/certs/ && cp /etc/letsencrypt/live/app.card2contacts.com/privkey.pem /opt/digicard/certs/ && docker-compose -f /opt/digicard/docker-compose.production.yml restart frontend"
```

---

## Step 5: Configure Environment Variables

### 5.1 Generate Secure Passwords

```bash
# Generate database password
openssl rand -base64 32

# Generate secret key
openssl rand -hex 32
```

### 5.2 Create .env.production File

```bash
cd /opt/digicard
cp .env.production .env.production.local
nano .env.production.local
```

Update these critical values in .env.production.local, then copy the contents to .env.production:

```env
# Database password (use the one you generated)
POSTGRES_PASSWORD=<your-generated-password>

# Secret key (use the one you generated)
SECRET_KEY=<your-generated-secret-key>

# Google OAuth credentials (from Google Cloud Console)
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>

# API Keys
GROQ_API_KEY=<your-groq-api-key>
MISTRAL_API_KEY=<your-mistral-api-key>

# Email configuration
SMTP_USER=<your-email>
SMTP_PASSWORD=<your-email-password>
```

### 5.3 Update docker-compose.yml

```bash
nano docker-compose.production.yml
```

Update the database password reference:

```yaml
services:
  db:
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

  backend:
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@db:5432/scanner_prod
```

---

## Step 6: Build and Deploy

### 6.1 Build Containers

```bash
cd /opt/digicard
docker-compose -f docker-compose.production.yml build
```

### 6.2 Start Services

```bash
docker-compose -f docker-compose.production.yml up -d
```

### 6.3 Check Logs

```bash
# View all logs
docker-compose -f docker-compose.production.yml logs -f

# View specific service logs
docker-compose -f docker-compose.production.yml logs -f backend
docker-compose -f docker-compose.production.yml logs -f db
```

### 6.4 Verify Services

```bash
# Check running containers
docker-compose -f docker-compose.production.yml ps

# Test database connection
docker-compose -f docker-compose.production.yml exec db pg_isready -U admin

# Check backend health (will show 404 if root path not configured, that's normal)
curl -I http://localhost:8000
```

---

## Step 7: Configure Firewall

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

## Step 8: Initial Setup

### 8.1 Enter Backend Container

```bash
docker-compose -f docker-compose.production.yml exec backend bash
```

### 8.2 Create Admin User

```bash
python backend/create_app_owner.py
```

Follow the prompts to create the application owner account. The admin panel URL will be displayed after creation.

Follow the prompts to create the application owner account.

### 8.3 Create Enterprise Admin (Optional)

```bash
python backend/create_enterprise_admin.py
```

### 8.4 Exit Container

```bash
exit
```

---

## Step 9: Verify Deployment

### 9.1 Access the Application

- Main App: https://app.card2contacts.com
- Admin Panel: https://app.card2contacts.com/admin.html
- API Documentation: https://app.card2contacts.com/api/docs

### 9.2 Test Key Features

1. **Login with Google OAuth**
2. **Upload and scan a business card**
3. **Verify OCR and AI extraction**
4. **Test admin panel functionality**

---

## Step 10: Set Up Monitoring

### 10.1 Make Backup Script Executable

The backup.sh script is already included in the repository. Just make it executable:

```bash
chmod +x /opt/digicard/backup.sh
```

### 10.2 Schedule Daily Backups

```bash
sudo crontab -e
```

Add:

```
0 2 * * * /opt/digicard/backup.sh >> /opt/digicard/backup.log 2>&1
```

---

## Step 11: Configure Docker Auto-Restart (Optional)

Create systemd service for Docker Compose (optional, for automatic restart on server reboot):

```bash
sudo nano /etc/systemd/system/digicard.service
```

```ini
[Unit]
Description=DigiCard Enterprise Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/digicard
ExecStart=/usr/local/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.production.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable digicard.service
sudo systemctl start digicard.service
```

**Note:** If you don't create this service, the containers will still run with `restart: always` policy, but won't automatically start on server reboot.

---

## Common Issues and Solutions

### Issue 1: SSL Certificate Errors

**Solution:**
```bash
# Renew certificate
sudo certbot renew --force-renewal

# Copy new certificates
sudo cp /etc/letsencrypt/live/app.card2contacts.com/fullchain.pem /opt/digicard/certs/
sudo cp /etc/letsencrypt/live/app.card2contacts.com/privkey.pem /opt/digicard/certs/

# Restart frontend
docker-compose -f docker-compose.production.yml restart frontend
```

### Issue 2: Database Connection Failed

**Solution:**
```bash
# Check if database is running
docker-compose -f docker-compose.production.yml ps db

# Check database logs
docker-compose -f docker-compose.production.yml logs db

# Verify DATABASE_URL in .env.production.local
docker-compose -f docker-compose.production.yml exec backend bash
echo $DATABASE_URL
```

### Issue 3: Container Won't Start

**Solution:**
```bash
# Check logs
docker-compose -f docker-compose.production.yml logs

# Rebuild containers
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

### Issue 4: Out of Disk Space

**Solution:**
```bash
# Clean Docker system
docker system prune -a

# Check disk usage
df -h

# Clean old logs
docker-compose -f docker-compose.production.yml logs --tail=0
```

---

## Updating the Application

When you need to update the code:

```bash
cd /opt/digicard

# Pull latest changes
git pull

# Rebuild and restart
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d

# Check logs
docker-compose -f docker-compose.production.yml logs -f
```

---

## Security Checklist

Before going to production, ensure:

- [ ] SSL certificate is properly configured
- [ ] `.env.production.local` created with production values
- [ ] POSTGRES_PASSWORD is set to strong random string
- [ ] SECRET_KEY is set to a strong random value
- [ ] GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET configured
- [ ] GROQ_API_KEY and MISTRAL_API_KEY configured
- [ ] SMTP credentials configured
- [ ] Firewall is configured (only 80, 443 open)
- [ ] Database is not accessible from outside (only 127.0.0.1:5432)
- [ ] ALLOWED_ORIGINS is restricted to `https://app.card2contacts.com`
- [ ] Regular backups are configured
- [ ] SSL auto-renewal is set up
- [ ] API keys are not committed to git
- [ ] Docker images are built and running
- [ ] Admin user created via `create_app_owner.py`

---

## File Structure After Deployment

```
/opt/digicard/
├── Dockerfile
├── Dockerfile.frontend
├── docker-compose.production.yml
├── nginx-production.conf
├── .env.production.local (not committed to git)
├── .env.production (template)
├── certs/
│   ├── fullchain.pem
│   └── privkey.pem
├── backups/
│   └── db_backup_*.sql.gz
├── backend/
├── frontend/
└── backup.sh
```

---

## Support and Troubleshooting

For more help:

1. Check logs: `docker-compose -f docker-compose.production.yml logs -f`
2. Review configuration files in the repository
3. Check the PRODUCTION_DEPLOYMENT.md and ADMIN_SETUP_GUIDE.md files
4. Monitor system resources: `htop`, `docker stats`

---

## Quick Reference Commands

```bash
# Start services
docker-compose -f docker-compose.production.yml up -d

# Stop services
docker-compose -f docker-compose.production.yml down

# Restart services
docker-compose -f docker-compose.production.yml restart

# View logs
docker-compose -f docker-compose.production.yml logs -f

# Backup database
./backup.sh

# Update application
git pull && docker-compose -f docker-compose.production.yml up -d --build

# Check container status
docker-compose -f docker-compose.production.yml ps

# Enter backend container
docker-compose -f docker-compose.production.yml exec backend bash
```
