# DigiCard Enterprise - Production Deployment Guide

Complete guide for deploying DigiCard Enterprise to production using Docker.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Server Requirements](#server-requirements)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Deployment Steps](#deployment-steps)
5. [SSL/TLS Configuration](#ssltls-configuration)
6. [Environment Configuration](#environment-configuration)
7. [Database Management](#database-management)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Troubleshooting](#troubleshooting)
10. [Security Best Practices](#security-best-practices)

---

## Prerequisites

### Required Software

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Git**: For cloning the repository
- **OpenSSL**: For certificate generation

### Installation Commands

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt-get install docker-compose-plugin

# Verify installation
docker --version
docker-compose --version
```

---

## Server Requirements

### Minimum Specifications

- **CPU**: 2 cores (4 recommended)
- **RAM**: 4GB (8GB recommended)
- **Storage**: 50GB SSD
- **Network**: Static IP address with open ports 80, 443

### Recommended Specifications (Production)

- **CPU**: 4+ cores
- **RAM**: 16GB+
- **Storage**: 100GB+ SSD
- **Network**: CDN integration, DDoS protection

### Firewall Configuration

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SSH (if needed)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

---

## Pre-Deployment Checklist

### 1. Domain Configuration

- [ ] Domain purchased and DNS configured
- [ ] A record pointing to server IP
- [ ] CNAME record for www subdomain (optional)
- [ ] DNS propagation completed (check with `dig yourdomain.com`)

### 2. API Keys & Credentials

Obtain the following API keys before deployment:

- [ ] **Google OAuth**: [Get credentials](https://console.cloud.google.com/apis/credentials)
  - Client ID
  - Client Secret
  - Authorized redirect URI: `https://yourdomain.com/api/auth/google/callback`

- [ ] **Groq API**: [Get API key](https://console.groq.com/keys)
  - For AI/LLM functionality

- [ ] **Mistral API**: [Get API key](https://console.mistral.ai/api-keys)
  - For OCR functionality

- [ ] **Gemini API** (Optional): [Get API key](https://makersuite.google.com/app/apikey)
  - Alternative AI provider

### 3. Security

- [ ] Generate strong SECRET_KEY: `openssl rand -hex 32`
- [ ] Create secure database password
- [ ] Set up SSH key authentication
- [ ] Disable root SSH login
- [ ] Configure firewall rules

---

## Deployment Steps

### Step 1: Clone Repository

```bash
# SSH to your production server
ssh user@your-server-ip

# Clone the repository
git clone https://github.com/yourusername/digicard-enterprise.git
cd digicard-enterprise

# Or transfer files using rsync/scp (see below)
```

### Step 2: Transfer Files to Production Server

If you're deploying from your local machine:

```bash
# Using rsync (recommended)
rsync -avz --exclude '.git' --exclude '__pycache__' \
  /path/to/local/digicard-enterprise/ \
  user@your-server-ip:/path/to/production/

# Using scp
tar -czf digicard.tar.gz /path/to/digicard-enterprise
scp digicard.tar.gz user@your-server-ip:/path/to/production/
ssh user@your-server-ip "cd /path/to/production && tar -xzf digicard.tar.gz"

# Using Docker save/load (if images are pre-built)
docker save digicard-backend:latest | gzip > backend.tar.gz
docker save digicard-frontend:latest | gzip > frontend.tar.gz
scp backend.tar.gz frontend.tar.gz user@your-server-ip:/path/to/production/
ssh user@your-server-ip "cd /path/to/production && docker load < backend.tar.gz && docker load < frontend.tar.gz"
```

### Step 3: Configure Environment

```bash
# Copy and edit production environment file
cp .env.example .env.production
nano .env.production
```

Update all required values in `.env.production`:

```bash
# CRITICAL: Update these values
ENVIRONMENT=production
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://yourdomain.com
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DB_USER=digicard_admin
DB_PASSWORD=<STRONG_PASSWORD_HERE>
DB_NAME=digicard_enterprise

# Security
SECRET_KEY=<GENERATED_SECRET_KEY_HERE>

# Google OAuth
GOOGLE_CLIENT_ID=<YOUR_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<YOUR_CLIENT_SECRET>
REDIRECT_URI=https://yourdomain.com/api/auth/google/callback

# AI/LLM
GROQ_API_KEY=<YOUR_GROQ_API_KEY>

# OCR
MISTRAL_API_KEY=<YOUR_MISTRAL_API_KEY>
```

### Step 4: Configure Frontend

Update [frontend/config.js](frontend/config.js) with production values:

```javascript
const CONFIG = {
    API_BASE_URL: 'https://yourdomain.com/api',
    FRONTEND_URL: 'https://yourdomain.com',
    GOOGLE_CLIENT_ID: 'your-client-id.apps.googleusercontent.com'
};
```

### Step 5: SSL Certificate Setup

#### Option A: Let's Encrypt (Recommended for Production)

```bash
# Make script executable
chmod +x scripts/setup-letsencrypt.sh

# Run Let's Encrypt setup
./scripts/setup-letsencrypt.sh

# Follow the prompts:
# - Enter your domain name
# - Enter your email address
```

#### Option B: Self-Signed Certificate (Testing Only)

```bash
# Make script executable
chmod +x scripts/generate-ssl-cert.sh

# Generate self-signed certificate
./scripts/generate-ssl-cert.sh

# Follow the prompts
```

#### Option C: Custom Certificate

```bash
# Create ssl directory
mkdir -p ssl

# Copy your certificates
cp /path/to/your/certificate.crt ssl/cert.pem
cp /path/to/your/private.key ssl/key.pem

# Set proper permissions
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem
```

### Step 6: Deploy Application

```bash
# Make deployment script executable
chmod +x scripts/deploy.sh

# Run deployment
./scripts/deploy.sh
```

The deployment script will:
1. Pull base Docker images
2. Build application images
3. Stop existing containers
4. Start all services
5. Verify health checks

### Step 7: Verify Deployment

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Test endpoints
curl http://localhost/health
curl https://yourdomain.com/health
curl https://yourdomain.com/api/health
```

### Step 8: Access Application

Open your browser and navigate to:
- **Frontend**: `https://yourdomain.com`
- **API Docs**: `https://yourdomain.com/api/docs`

---

## SSL/TLS Configuration

### Let's Encrypt Auto-Renewal

The Certbot container automatically renews certificates every 12 hours.

To manually renew:

```bash
docker-compose run --rm certbot renew
docker-compose restart frontend
```

### Certificate Expiry Monitoring

```bash
# Check certificate expiry
openssl x509 -in ssl/cert.pem -noout -dates

# Set up cron job for expiry alerts (optional)
0 0 * * * /path/to/check-cert-expiry.sh
```

### Using External Load Balancer

If using AWS ALB, Cloudflare, or similar:

1. Configure SSL termination at the load balancer
2. Use HTTP between load balancer and application
3. Update `nginx/default.conf` to accept forwarded HTTPS headers

---

## Environment Configuration

### Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `ENVIRONMENT` | Deployment environment | Yes |
| `FRONTEND_URL` | Frontend URL | Yes |
| `BACKEND_URL` | Backend API URL | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | JWT secret key (min 32 chars) | Yes |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | Yes |
| `GROQ_API_KEY` | Groq API key for LLM | Yes |
| `MISTRAL_API_KEY` | Mistral API key for OCR | Yes |
| `GEMINI_API_KEY` | Gemini API key (optional) | No |
| `FREE_TIER_SCAN_LIMIT` | Free tier scan limit | No |

### Updating Configuration

```bash
# Edit environment file
nano .env.production

# Restart services to apply changes
docker-compose restart backend
```

---

## Database Management

### Backup Database

```bash
# Make backup script executable
chmod +x scripts/backup.sh

# Create backup
./scripts/backup.sh

# Backups are stored in: backups/digicard_backup_YYYYMMDD_HHMMSS.sql.gz
```

### Restore Database

```bash
# Make restore script executable
chmod +x scripts/restore.sh

# Restore from backup
./scripts/restore.sh backups/digicard_backup_20240115_120000.sql.gz
```

### Manual Database Operations

```bash
# Access database CLI
docker exec -it digicard-database psql -U digicard_admin -d digicard_enterprise

# Export database
docker exec digicard-database pg_dump -U digicard_admin digicard_enterprise > backup.sql

# Import database
docker exec -i digicard-database psql -U digicard_admin digicard_enterprise < backup.sql
```

### Automated Backups

Set up daily backups using cron:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /path/to/digicard-enterprise && ./scripts/backup.sh >> /var/log/digicard-backup.log 2>&1
```

---

## Monitoring & Maintenance

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f database

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Resource Monitoring

```bash
# Container resource usage
docker stats

# Disk usage
docker system df

# Clean up unused resources
docker system prune -a
```

### Health Checks

```bash
# Service health status
docker-compose ps

# Manual health checks
curl http://localhost/health
curl http://localhost:8000/health
```

### Updating the Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build
docker-compose up -d

# Or use deployment script
./scripts/deploy.sh
```

### Scaling

```bash
# Scale backend workers
docker-compose up -d --scale backend=3

# Note: Requires load balancer configuration
```

---

## Troubleshooting

### Common Issues

#### 1. Services Won't Start

```bash
# Check logs
docker-compose logs

# Check Docker daemon
systemctl status docker

# Restart Docker
sudo systemctl restart docker
```

#### 2. Database Connection Errors

```bash
# Verify database is running
docker-compose ps database

# Check database logs
docker-compose logs database

# Verify connection string in .env.production
# Should match: postgresql://DB_USER:DB_PASSWORD@database:5432/DB_NAME
```

#### 3. SSL Certificate Issues

```bash
# Verify certificate files exist
ls -l ssl/

# Check certificate validity
openssl x509 -in ssl/cert.pem -text -noout

# Regenerate self-signed certificate
./scripts/generate-ssl-cert.sh
```

#### 4. Port Already in Use

```bash
# Find process using port
sudo lsof -i :80
sudo lsof -i :443

# Stop conflicting service
sudo systemctl stop nginx  # if nginx is installed
sudo systemctl stop apache2  # if apache is installed
```

#### 5. Permission Denied Errors

```bash
# Fix ownership
sudo chown -R $USER:$USER .

# Fix script permissions
chmod +x scripts/*.sh
```

### Debug Mode

Enable debug logging:

```bash
# Edit .env.production
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart backend
```

### Getting Help

- Check logs: `docker-compose logs -f`
- Review configuration files
- Verify all environment variables are set
- Ensure API keys are valid
- Check firewall rules

---

## Security Best Practices

### 1. Secrets Management

- Never commit `.env.production` to git
- Use strong, unique passwords
- Rotate secrets regularly
- Consider using Docker secrets or external secret managers

### 2. Network Security

```bash
# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Regular Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker-compose pull
docker-compose up -d
```

### 4. Access Control

- Disable root SSH access
- Use SSH keys instead of passwords
- Implement fail2ban for brute force protection
- Use VPN for database access

### 5. Monitoring & Alerts

- Set up log monitoring
- Configure uptime monitoring
- Enable database backup alerts
- Monitor disk space and resource usage

### 6. CORS Configuration

Restrict CORS origins in `.env.production`:

```bash
# Don't use wildcard in production
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 7. Rate Limiting

Configure rate limits to prevent abuse:

```bash
RATE_LIMIT_PER_MINUTE=60
BULK_SCAN_MAX_FILES=100
```

---

## Quick Reference

### Essential Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Backup database
./scripts/backup.sh

# Deploy/update
./scripts/deploy.sh
```

### Directory Structure

```
digicard-enterprise/
├── backend/              # Backend application code
├── frontend/             # Frontend application code
├── nginx/                # Nginx configuration
├── scripts/              # Deployment and maintenance scripts
├── ssl/                  # SSL certificates
├── database/             # Database initialization
├── docker-compose.yml    # Docker orchestration
├── Dockerfile.backend    # Backend container definition
├── Dockerfile.frontend   # Frontend container definition
├── .env.production       # Production environment variables
└── requirements.txt      # Python dependencies
```

---

## Support

For issues and questions:
1. Check this deployment guide
2. Review application logs
3. Consult the troubleshooting section
4. Contact the development team

---

**Last Updated**: January 2025
**Version**: 1.0.0
