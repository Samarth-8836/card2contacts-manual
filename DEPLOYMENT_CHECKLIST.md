# DigiCard Enterprise - Production Deployment Checklist

Use this checklist to ensure a smooth production deployment.

## Pre-Deployment Checklist

### 1. Server Setup ✅

- [ ] Server provisioned (4GB+ RAM, 50GB+ storage)
- [ ] Ubuntu 20.04+ / Debian 11+ installed
- [ ] Static IP address assigned
- [ ] Firewall configured (ports 80, 443, 22)
- [ ] SSH access configured with key authentication
- [ ] Non-root user with sudo privileges created

### 2. Docker Installation ✅

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Verify installation
docker --version
docker-compose --version

# Add user to docker group
sudo usermod -aG docker $USER
```

- [ ] Docker installed (version 20.10+)
- [ ] Docker Compose installed (version 2.0+)
- [ ] Docker service running
- [ ] User added to docker group

### 3. Domain & DNS ✅

- [ ] Domain name purchased
- [ ] A record created pointing to server IP
- [ ] CNAME record for www subdomain (optional)
- [ ] DNS propagation completed (test with `dig yourdomain.com`)
- [ ] TTL set appropriately (3600 seconds recommended)

### 4. API Keys & Credentials ✅

#### Google OAuth
- [ ] Google Cloud project created
- [ ] OAuth 2.0 credentials created
- [ ] Client ID obtained
- [ ] Client secret obtained
- [ ] Authorized redirect URI added: `https://yourdomain.com/api/auth/google/callback`
- [ ] Test credentials working

Link: https://console.cloud.google.com/apis/credentials

#### Groq API (LLM)
- [ ] Groq account created
- [ ] API key generated
- [ ] Test API key working

Link: https://console.groq.com/keys

#### Mistral API (OCR)
- [ ] Mistral account created
- [ ] API key generated
- [ ] Test API key working

Link: https://console.mistral.ai/api-keys

#### Optional: Gemini API
- [ ] Gemini API key obtained (if using Gemini models)

Link: https://makersuite.google.com/app/apikey

### 5. Security ✅

- [ ] Strong SECRET_KEY generated: `openssl rand -hex 32`
- [ ] Strong database password created
- [ ] SSH keys configured (disable password auth)
- [ ] Firewall rules configured
- [ ] fail2ban installed and configured (optional)
- [ ] Root SSH login disabled

---

## Deployment Checklist

### 1. Transfer Application ✅

Choose one method:

**Method A: Git Clone**
```bash
ssh user@your-server-ip
git clone https://github.com/yourusername/digicard-enterprise.git
cd digicard-enterprise
```

**Method B: Rsync**
```bash
rsync -avz --exclude '.git' --exclude '__pycache__' \
  ./digicard-enterprise/ \
  user@your-server-ip:/opt/digicard-enterprise/
```

**Method C: SCP**
```bash
tar --exclude='.git' --exclude='__pycache__' -czf digicard.tar.gz digicard-enterprise/
scp digicard.tar.gz user@your-server-ip:/opt/
ssh user@your-server-ip "cd /opt && tar -xzf digicard.tar.gz"
```

- [ ] Application files transferred to server
- [ ] Correct directory structure verified
- [ ] File permissions correct

### 2. Configure Environment ✅

```bash
cd /opt/digicard-enterprise
cp .env.example .env.production
nano .env.production
```

Update these **CRITICAL** values:

```env
# Deployment
ENVIRONMENT=production
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://yourdomain.com
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DB_USER=digicard_admin
DB_PASSWORD=<YOUR_STRONG_PASSWORD>
DB_NAME=digicard_enterprise

# Security
SECRET_KEY=<YOUR_GENERATED_SECRET_KEY>

# Google OAuth
GOOGLE_CLIENT_ID=<YOUR_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<YOUR_CLIENT_SECRET>
REDIRECT_URI=https://yourdomain.com/api/auth/google/callback

# API Keys
GROQ_API_KEY=<YOUR_GROQ_KEY>
MISTRAL_API_KEY=<YOUR_MISTRAL_KEY>
```

- [ ] .env.production created from template
- [ ] All required environment variables filled
- [ ] URLs updated with production domain
- [ ] API keys validated
- [ ] Strong passwords set

### 3. Configure Frontend ✅

```bash
nano frontend/config.js
```

Update:
```javascript
const CONFIG = {
    API_BASE_URL: 'https://yourdomain.com/api',
    FRONTEND_URL: 'https://yourdomain.com',
    GOOGLE_CLIENT_ID: 'your-client-id.apps.googleusercontent.com'
};
```

- [ ] API_BASE_URL updated
- [ ] FRONTEND_URL updated
- [ ] GOOGLE_CLIENT_ID updated

### 4. SSL Certificate Setup ✅

Choose one option:

**Option A: Let's Encrypt (Production - Recommended)**
```bash
chmod +x scripts/setup-letsencrypt.sh
./scripts/setup-letsencrypt.sh
```
- [ ] Let's Encrypt certificates installed
- [ ] Auto-renewal configured

**Option B: Self-signed (Testing Only)**
```bash
chmod +x scripts/generate-ssl-cert.sh
./scripts/generate-ssl-cert.sh
```
- [ ] Self-signed certificate generated

**Option C: Custom Certificate**
```bash
mkdir -p ssl
cp your-cert.crt ssl/cert.pem
cp your-key.key ssl/key.pem
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem
```
- [ ] Custom certificates installed

Verify certificates:
```bash
ls -l ssl/
openssl x509 -in ssl/cert.pem -text -noout
```

- [ ] ssl/cert.pem exists
- [ ] ssl/key.pem exists
- [ ] Certificate valid and not expired
- [ ] Proper file permissions set

### 5. Deploy Application ✅

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Deploy
./scripts/deploy.sh
```

Or manually:
```bash
docker-compose build
docker-compose up -d
```

- [ ] Scripts made executable
- [ ] Docker images built successfully
- [ ] Containers started
- [ ] No build errors

### 6. Verify Deployment ✅

```bash
# Check service status
docker-compose ps

# All services should show "Up" status
# Expected services:
# - digicard-database
# - digicard-backend
# - digicard-frontend
# - digicard-certbot
```

- [ ] All services running
- [ ] Health checks passing
- [ ] No restart loops

### 7. Test Endpoints ✅

```bash
# Test health endpoints
curl http://localhost/health
curl http://localhost:8000/health

# Test HTTPS
curl https://yourdomain.com/health
curl https://yourdomain.com/api/health

# Test redirect
curl -I http://yourdomain.com
# Should return 301 redirect to HTTPS
```

- [ ] HTTP health endpoint responding
- [ ] Backend health endpoint responding
- [ ] HTTPS health endpoint responding
- [ ] HTTP to HTTPS redirect working
- [ ] SSL certificate valid in browser

### 8. Application Testing ✅

Open browser and test:

1. **Frontend Access**
   - [ ] Visit https://yourdomain.com
   - [ ] Page loads without errors
   - [ ] No SSL warnings
   - [ ] UI elements display correctly

2. **Authentication**
   - [ ] Google Sign-In button appears
   - [ ] Click "Sign in with Google"
   - [ ] OAuth flow completes
   - [ ] Successfully logged in

3. **Core Features**
   - [ ] Upload and scan business card
   - [ ] View scan results
   - [ ] Navigate admin panel
   - [ ] All features working

4. **API Documentation**
   - [ ] Visit https://yourdomain.com/api/docs
   - [ ] Swagger UI loads
   - [ ] API endpoints listed

### 9. Monitoring Setup ✅

```bash
# View real-time logs
docker-compose logs -f

# Check resource usage
docker stats

# Monitor disk space
df -h
```

- [ ] Logs accessible and readable
- [ ] Resource usage acceptable
- [ ] Disk space sufficient (>20GB free)

### 10. Backup Configuration ✅

```bash
# Test backup
./scripts/backup.sh

# Verify backup created
ls -lh backups/
```

Set up automated backups:
```bash
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /opt/digicard-enterprise && ./scripts/backup.sh >> /var/log/digicard-backup.log 2>&1
```

- [ ] Manual backup successful
- [ ] Backup file created in backups/
- [ ] Automated backup cron job added
- [ ] Backup log path configured

---

## Post-Deployment Checklist

### 1. Security Hardening ✅

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install fail2ban
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

- [ ] System packages updated
- [ ] fail2ban installed and running
- [ ] Firewall configured and enabled
- [ ] Unnecessary ports closed
- [ ] SSH hardened (key-only auth)

### 2. Monitoring & Alerts ✅

- [ ] Uptime monitoring configured (UptimeRobot, Pingdom, etc.)
- [ ] SSL expiry monitoring set up
- [ ] Disk space alerts configured
- [ ] Log aggregation set up (optional)
- [ ] Error alerting configured

### 3. Documentation ✅

- [ ] Production URLs documented
- [ ] Admin credentials stored securely
- [ ] API keys backed up securely
- [ ] Deployment procedure documented
- [ ] Team members trained

### 4. Compliance & Legal ✅

- [ ] Privacy policy updated
- [ ] Terms of service updated
- [ ] Cookie consent implemented (if required)
- [ ] GDPR compliance verified (if applicable)
- [ ] Data retention policy defined

---

## Maintenance Checklist

### Daily
- [ ] Check service status: `docker-compose ps`
- [ ] Review error logs: `docker-compose logs --tail=100`

### Weekly
- [ ] Review resource usage: `docker stats`
- [ ] Check disk space: `df -h`
- [ ] Verify backups created
- [ ] Test application functionality

### Monthly
- [ ] Update system packages: `sudo apt update && sudo apt upgrade`
- [ ] Update Docker images: `docker-compose pull && docker-compose up -d`
- [ ] Review and rotate logs
- [ ] Test backup restore procedure
- [ ] Review security advisories

### Quarterly
- [ ] Security audit
- [ ] Performance optimization review
- [ ] Backup retention review
- [ ] Update documentation
- [ ] Team training refresh

---

## Troubleshooting Quick Reference

### Services Won't Start
```bash
docker-compose logs
systemctl status docker
sudo systemctl restart docker
```

### Database Connection Errors
```bash
docker-compose logs database
docker-compose restart database
# Check DATABASE_URL in .env.production
```

### SSL Certificate Issues
```bash
ls -l ssl/
openssl x509 -in ssl/cert.pem -text -noout
./scripts/generate-ssl-cert.sh
```

### Port Conflicts
```bash
sudo lsof -i :80
sudo lsof -i :443
sudo systemctl stop nginx apache2
```

### High Resource Usage
```bash
docker stats
docker system prune -a
# Consider scaling up server
```

---

## Success Criteria

Your deployment is successful when:

- ✅ All services running: `docker-compose ps` shows "Up"
- ✅ HTTPS accessible: `https://yourdomain.com` loads
- ✅ No SSL warnings in browser
- ✅ Health checks passing
- ✅ Authentication working (Google Sign-In)
- ✅ Core features functional
- ✅ Backups configured and working
- ✅ Monitoring set up
- ✅ Security hardening complete

---

## Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| DevOps Lead | | |
| Backend Developer | | |
| System Administrator | | |
| Security Officer | | |

---

## Rollback Procedure

If deployment fails:

```bash
# Stop services
docker-compose down

# Restore from backup
./scripts/restore.sh backups/latest_backup.sql.gz

# Roll back to previous version
git checkout previous-version-tag
docker-compose build
docker-compose up -d
```

---

**Print this checklist and check off items as you complete them!**

**Last Updated**: January 2025
**Version**: 1.0.0
