# DigiCard Enterprise - Docker Quick Start

Get your application running in production in 15 minutes.

## Prerequisites

- Server with Docker and Docker Compose installed
- Domain name pointing to your server
- API keys ready (Google OAuth, Groq, Mistral)

## Quick Deployment Steps

### 1. Transfer Application

```bash
# From your local machine, transfer to production server
rsync -avz --exclude '.git' --exclude '__pycache__' \
  ./digicard-enterprise/ \
  user@your-server-ip:/opt/digicard-enterprise/
```

### 2. Configure Environment

```bash
# SSH to server
ssh user@your-server-ip
cd /opt/digicard-enterprise

# Create production config
cp .env.example .env.production
nano .env.production
```

**Minimum required values:**

```env
ENVIRONMENT=production
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://yourdomain.com
ALLOWED_ORIGINS=https://yourdomain.com

DB_PASSWORD=<STRONG_PASSWORD>
SECRET_KEY=<RUN: openssl rand -hex 32>

GOOGLE_CLIENT_ID=<YOUR_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<YOUR_CLIENT_SECRET>
REDIRECT_URI=https://yourdomain.com/api/auth/google/callback

GROQ_API_KEY=<YOUR_GROQ_KEY>
MISTRAL_API_KEY=<YOUR_MISTRAL_KEY>
```

### 3. Update Frontend Config

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

### 4. Setup SSL & Deploy

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Option A: Let's Encrypt (Production)
./scripts/setup-letsencrypt.sh
# Enter domain and email when prompted

# Option B: Self-signed (Testing)
./scripts/generate-ssl-cert.sh
# Enter domain when prompted

# Deploy application
./scripts/deploy.sh
```

### 5. Verify

```bash
# Check services
docker-compose ps

# View logs
docker-compose logs -f

# Test application
curl https://yourdomain.com/health
```

Visit: `https://yourdomain.com`

## Package for Transfer

If you want to create a single package to transfer:

```bash
# From your local machine
cd /path/to/digicard-enterprise

# Create deployment package
tar --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='node_modules' \
    -czf digicard-deployment-package.tar.gz .

# Transfer to server
scp digicard-deployment-package.tar.gz user@your-server-ip:/opt/

# On server, extract
ssh user@your-server-ip
cd /opt
mkdir -p digicard-enterprise
tar -xzf digicard-deployment-package.tar.gz -C digicard-enterprise
cd digicard-enterprise
```

## Using Pre-built Docker Images

If you want to build images locally and transfer them:

```bash
# Build images locally
docker-compose build

# Save images
docker save digicard-enterprise-backend:latest | gzip > backend-image.tar.gz
docker save digicard-enterprise-frontend:latest | gzip > frontend-image.tar.gz

# Transfer to server
scp backend-image.tar.gz frontend-image.tar.gz user@your-server-ip:/opt/digicard-enterprise/

# On server, load images
ssh user@your-server-ip
cd /opt/digicard-enterprise
docker load < backend-image.tar.gz
docker load < frontend-image.tar.gz

# Start services
docker-compose up -d
```

## Essential Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# Logs
docker-compose logs -f

# Status
docker-compose ps

# Backup
./scripts/backup.sh

# Update
git pull && ./scripts/deploy.sh
```

## Troubleshooting

### Ports in use
```bash
sudo lsof -i :80
sudo lsof -i :443
sudo systemctl stop nginx apache2
```

### Database issues
```bash
docker-compose logs database
docker-compose restart database
```

### Permission errors
```bash
chmod +x scripts/*.sh
sudo chown -R $USER:$USER .
```

## Need Help?

See full guide: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

**Ready in 15 minutes! 🚀**
