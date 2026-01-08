# DigiCard Enterprise - Docker Deployment

Production-ready Docker containerization for DigiCard Enterprise application.

## 📋 Overview

This deployment package includes:

- **Backend**: FastAPI application containerized with Python 3.11
- **Frontend**: Static files served via Nginx with HTTPS support
- **Database**: PostgreSQL 16 with automatic initialization
- **SSL/TLS**: Support for Let's Encrypt and custom certificates
- **Auto-renewal**: Automated certificate renewal with Certbot
- **Health Checks**: Built-in health monitoring for all services
- **Backup/Restore**: Automated database backup scripts

## 🚀 Quick Start

See [DOCKER_QUICK_START.md](DOCKER_QUICK_START.md) for 15-minute deployment guide.

## 📚 Documentation

- **[Deployment Guide](DEPLOYMENT_GUIDE.md)**: Complete production deployment guide
- **[Quick Start](DOCKER_QUICK_START.md)**: Fast deployment in 15 minutes
- **[Production Deployment](PRODUCTION_DEPLOYMENT.md)**: Original deployment notes
- **[Config Summary](CONFIG_SUMMARY.md)**: Configuration reference

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│         Internet (HTTPS/HTTP)               │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │  Nginx (Frontend) │
         │   - SSL/TLS       │
         │   - Static Files  │
         │   - Reverse Proxy │
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐
         │  FastAPI Backend  │
         │   - REST API      │
         │   - Auth          │
         │   - Business      │
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐
         │  PostgreSQL 16    │
         │   - Data Storage  │
         │   - Persistence   │
         └───────────────────┘
```

## 📦 What's Included

### Docker Configuration

- `Dockerfile.backend` - Backend container definition
- `Dockerfile.frontend` - Frontend container with Nginx
- `docker-compose.yml` - Multi-container orchestration
- `.dockerignore` - Build optimization

### Nginx Configuration

- `nginx/nginx.conf` - Main Nginx configuration
- `nginx/default.conf` - Server block with SSL/TLS and reverse proxy

### Scripts

- `scripts/deploy.sh` - One-command deployment
- `scripts/generate-ssl-cert.sh` - Self-signed certificate generator
- `scripts/setup-letsencrypt.sh` - Let's Encrypt certificate setup
- `scripts/backup.sh` - Database backup utility
- `scripts/restore.sh` - Database restore utility

### Configuration

- `.env.production` - Production environment template
- `.env.example` - Environment variable reference
- `requirements.txt` - Python dependencies
- `database/init.sql` - Database initialization

## 🔧 Prerequisites

### Server Requirements

- Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- 4GB RAM minimum (8GB recommended)
- 50GB storage minimum
- Docker 20.10+
- Docker Compose 2.0+

### External Services

- Domain name with DNS configured
- Google OAuth credentials
- Groq API key (for LLM)
- Mistral API key (for OCR)

## 📝 Configuration

### 1. Environment Variables

Copy and configure production environment:

```bash
cp .env.example .env.production
nano .env.production
```

Required variables:
- `FRONTEND_URL` - Your domain URL
- `BACKEND_URL` - API URL (usually same as frontend)
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT secret (generate with `openssl rand -hex 32`)
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth secret
- `GROQ_API_KEY` - Groq API key
- `MISTRAL_API_KEY` - Mistral OCR API key

### 2. Frontend Configuration

Update `frontend/config.js`:

```javascript
const CONFIG = {
    API_BASE_URL: 'https://yourdomain.com/api',
    FRONTEND_URL: 'https://yourdomain.com',
    GOOGLE_CLIENT_ID: 'your-client-id.apps.googleusercontent.com'
};
```

### 3. SSL Certificates

Choose one method:

**Let's Encrypt (Recommended)**:
```bash
./scripts/setup-letsencrypt.sh
```

**Self-signed (Testing)**:
```bash
./scripts/generate-ssl-cert.sh
```

**Custom Certificate**:
```bash
cp your-cert.crt ssl/cert.pem
cp your-key.key ssl/key.pem
```

## 🎯 Deployment

### Standard Deployment

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Deploy
./scripts/deploy.sh
```

### Manual Deployment

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## 🔒 Security Features

- HTTPS/TLS encryption
- Automatic certificate renewal
- Non-root container users
- Security headers (HSTS, XSS protection, etc.)
- CORS restrictions
- Rate limiting
- SQL injection protection
- XSS prevention
- CSRF protection

## 📊 Monitoring

### Health Checks

```bash
# Service health
docker-compose ps

# Application health
curl http://localhost/health
curl http://localhost:8000/health
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f database
```

### Resource Usage

```bash
# Real-time stats
docker stats

# Disk usage
docker system df
```

## 💾 Backup & Restore

### Backup

```bash
# Create backup
./scripts/backup.sh

# Backups stored in: backups/digicard_backup_YYYYMMDD_HHMMSS.sql.gz
```

### Restore

```bash
# Restore from backup
./scripts/restore.sh backups/digicard_backup_20240115_120000.sql.gz
```

### Automated Backups

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * cd /path/to/digicard-enterprise && ./scripts/backup.sh
```

## 🔄 Updates

### Application Updates

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d

# Or use deploy script
./scripts/deploy.sh
```

### System Updates

```bash
# Update base images
docker-compose pull

# Rebuild application
docker-compose build --no-cache

# Restart services
docker-compose up -d
```

## 🐛 Troubleshooting

### Services won't start

```bash
docker-compose logs
systemctl status docker
```

### Database connection errors

```bash
docker-compose logs database
docker-compose restart database
```

### SSL certificate issues

```bash
ls -l ssl/
openssl x509 -in ssl/cert.pem -text -noout
```

### Port conflicts

```bash
sudo lsof -i :80
sudo lsof -i :443
```

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed troubleshooting.

## 📂 Directory Structure

```
digicard-enterprise/
├── backend/                  # Backend application
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── database.py          # Database models
│   └── ...                  # Other modules
├── frontend/                 # Frontend files
│   ├── index.html           # Main page
│   ├── admin.html           # Admin page
│   ├── config.js            # Frontend config
│   └── ...                  # Other assets
├── nginx/                    # Nginx configuration
│   ├── nginx.conf           # Main config
│   └── default.conf         # Server config
├── scripts/                  # Deployment scripts
│   ├── deploy.sh            # Main deployment
│   ├── backup.sh            # Database backup
│   ├── restore.sh           # Database restore
│   ├── generate-ssl-cert.sh # SSL certificate generator
│   └── setup-letsencrypt.sh # Let's Encrypt setup
├── database/                 # Database initialization
│   └── init.sql             # Init script
├── ssl/                      # SSL certificates (gitignored)
├── docker-compose.yml        # Container orchestration
├── Dockerfile.backend        # Backend container
├── Dockerfile.frontend       # Frontend container
├── .env.production          # Production config (gitignored)
├── .dockerignore            # Docker build exclusions
├── requirements.txt         # Python dependencies
├── DEPLOYMENT_GUIDE.md      # Full deployment guide
└── DOCKER_QUICK_START.md    # Quick start guide
```

## 🔗 Useful Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f [service]

# Execute command in container
docker-compose exec backend bash
docker-compose exec database psql -U digicard_admin

# Scale services
docker-compose up -d --scale backend=3

# Clean up
docker system prune -a
```

## 📞 Support

For issues and questions:

1. Check the [Deployment Guide](DEPLOYMENT_GUIDE.md)
2. Review logs: `docker-compose logs -f`
3. Check troubleshooting section
4. Contact development team

## 📄 License

See LICENSE file for details.

## 🎉 Success Checklist

- [ ] Docker and Docker Compose installed
- [ ] Domain DNS configured
- [ ] API keys obtained
- [ ] .env.production configured
- [ ] frontend/config.js updated
- [ ] SSL certificates generated/installed
- [ ] Application deployed: `./scripts/deploy.sh`
- [ ] Services running: `docker-compose ps`
- [ ] Application accessible: `https://yourdomain.com`
- [ ] Backup configured: `./scripts/backup.sh`
- [ ] Monitoring set up

---

**Version**: 1.0.0
**Last Updated**: January 2025
**Status**: Production Ready ✅
