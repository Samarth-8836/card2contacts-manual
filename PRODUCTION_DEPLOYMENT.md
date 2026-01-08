# DigiCard Enterprise - Production Deployment Guide

## Overview

This guide will help you deploy DigiCard Enterprise to a production server. All configuration has been centralized to make deployment easier.

## Configuration Files

### Backend Configuration
- **File**: `backend/config.py` - Central configuration for all backend settings
- **Environment File**: `.env` - Contains sensitive credentials and environment-specific values

### Frontend Configuration
- **File**: `frontend/config.js` - Central configuration for all frontend settings

## Pre-Deployment Checklist

### 1. Environment Variables (.env file)

Copy `.env.example` to `.env` and update the following values:

```bash
cp .env.example .env
```

#### Critical Values to Change:

1. **ENVIRONMENT** - Set to `production`
2. **FRONTEND_URL** - Your production frontend URL (e.g., `https://yourdomain.com`)
3. **BACKEND_URL** - Your production backend URL (same as frontend for single-server setup)
4. **ALLOWED_ORIGINS** - Restrict to your actual domains (e.g., `https://yourdomain.com,https://www.yourdomain.com`)
5. **DATABASE_URL** - Production PostgreSQL connection string
6. **SECRET_KEY** - Generate a strong random key:
   ```bash
   openssl rand -hex 32
   ```
7. **REDIRECT_URI** - Update with production domain (e.g., `https://yourdomain.com/api/auth/google/callback`)
8. **GOOGLE_CLIENT_ID** and **GOOGLE_CLIENT_SECRET** - Production OAuth credentials
9. **API Keys** - Set the appropriate AI and OCR service keys:
   - `GROQ_API_KEY` or `GEMINI_API_KEY` (depending on your AI model choice)
   - `MISTRAL_API_KEY` (for OCR)

#### Business Logic Settings (Optional):

- **FREE_TIER_SCAN_LIMIT** - Number of free scans for unlicensed users (default: 4)
- **DEFAULT_MAX_SUB_ACCOUNTS** - Default sub-accounts for enterprise licenses (default: 5)
- **LLM_MODEL** - AI model to use (default: `groq/llama-3.1-8b-instant`)
- **OCR_PROVIDER** - OCR provider to use (default: `mistral`)
- **MISTRAL_MODEL** - Mistral OCR model (default: `mistral-ocr-2512`)

### 2. Frontend Configuration (frontend/config.js)

Update the following values in `frontend/config.js`:

```javascript
const CONFIG = {
    ENVIRONMENT: 'production',
    API_BASE_URL: '',  // Empty for same-origin, or set to backend URL if different
    FRONTEND_URL: 'https://yourdomain.com',
    ENABLE_CONSOLE_LOGS: false,  // Disable in production
    ENABLE_ERROR_REPORTING: true,  // Enable if using error reporting service
};
```

### 3. Google OAuth Configuration

Update your Google Cloud Console OAuth client:

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Update **Authorized JavaScript origins**:
   - Add your production domain: `https://yourdomain.com`
3. Update **Authorized redirect URIs**:
   - Add: `https://yourdomain.com/api/auth/google/callback`
4. Copy the Client ID and Secret to your `.env` file

### 4. SSL/TLS Certificates

Ensure your server has valid SSL/TLS certificates installed. Use Let's Encrypt for free certificates:

```bash
# Example using Certbot
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 5. Database Setup

1. Create production PostgreSQL database:
   ```sql
   CREATE DATABASE scanner_prod;
   CREATE USER admin WITH PASSWORD 'your-secure-password';
   GRANT ALL PRIVILEGES ON DATABASE scanner_prod TO admin;
   ```

2. Update `DATABASE_URL` in `.env` with production credentials

3. Run database migrations (if any)

## Configuration Summary

### Files to Update for Production:

| File | What to Change |
|------|----------------|
| `.env` | All environment variables (see `.env.example`) |
| `frontend/config.js` | `ENVIRONMENT`, `FRONTEND_URL`, `API_BASE_URL` |
| Google Cloud Console | OAuth redirect URIs for production domain |

### Single Points of Configuration:

| Setting | Location | Purpose |
|---------|----------|---------|
| Backend URL | `.env` → `BACKEND_URL` | API endpoint URL |
| Frontend URL | `.env` → `FRONTEND_URL` & `frontend/config.js` → `FRONTEND_URL` | Application URL |
| CORS Origins | `.env` → `ALLOWED_ORIGINS` | Allowed origins for API requests |
| Database | `.env` → `DATABASE_URL` | PostgreSQL connection |
| AI Model | `.env` → `LLM_MODEL` | Which AI model to use |
| OCR Provider | `.env` → `OCR_PROVIDER` | Which OCR service to use |
| Free Tier Limit | `.env` → `FREE_TIER_SCAN_LIMIT` | Number of free scans |
| Google OAuth | `.env` → `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | OAuth credentials |

## Deployment Steps

### Option 1: Manual Deployment

1. **Prepare the server:**
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y

   # Install Python 3.11+
   sudo apt install python3.11 python3.11-venv python3-pip -y

   # Install PostgreSQL
   sudo apt install postgresql postgresql-contrib -y

   # Install Nginx (for serving frontend and reverse proxy)
   sudo apt install nginx -y
   ```

2. **Clone and setup the application:**
   ```bash
   cd /var/www
   git clone <your-repo-url> digicard
   cd digicard

   # Create virtual environment
   python3.11 -m venv venv
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   # Copy and edit .env file
   cp .env.example .env
   nano .env  # Edit with production values

   # Edit frontend config
   nano frontend/config.js  # Update production values
   ```

4. **Setup systemd service for backend:**
   ```bash
   sudo nano /etc/systemd/system/digicard.service
   ```

   Add:
   ```ini
   [Unit]
   Description=DigiCard Enterprise Backend
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/var/www/digicard
   Environment="PATH=/var/www/digicard/venv/bin"
   ExecStart=/var/www/digicard/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Enable and start:
   ```bash
   sudo systemctl enable digicard
   sudo systemctl start digicard
   sudo systemctl status digicard
   ```

5. **Configure Nginx:**
   ```bash
   sudo nano /etc/nginx/sites-available/digicard
   ```

   Add:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com www.yourdomain.com;
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name yourdomain.com www.yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

       # Frontend static files
       location / {
           root /var/www/digicard/frontend;
           try_files $uri $uri/ /index.html;
       }

       # Backend API
       location /api {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

   Enable site:
   ```bash
   sudo ln -s /etc/nginx/sites-available/digicard /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### Option 2: Docker Deployment

Create `docker-compose.production.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: scanner_prod
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  backend:
    build: .
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000
    env_file:
      - .env
    depends_on:
      - postgres
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./frontend:/usr/share/nginx/html
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
    restart: always

volumes:
  postgres_data:
```

Deploy:
```bash
docker-compose -f docker-compose.production.yml up -d
```

## Post-Deployment Verification

1. **Test backend health:**
   ```bash
   curl https://yourdomain.com/api/
   ```

2. **Test frontend loading:**
   - Visit `https://yourdomain.com` in browser
   - Check browser console for errors

3. **Test Google OAuth:**
   - Try logging in with Google
   - Verify redirect works correctly

4. **Test scanning:**
   - Upload a test business card
   - Verify OCR and AI processing work

5. **Check logs:**
   ```bash
   # Backend logs
   sudo journalctl -u digicard -f

   # Nginx logs
   sudo tail -f /var/log/nginx/access.log
   sudo tail -f /var/log/nginx/error.log
   ```

## Common Issues

### Issue: CORS errors in browser console
**Solution**: Check `ALLOWED_ORIGINS` in `.env` includes your production domain

### Issue: Google OAuth redirect fails
**Solution**: Verify `REDIRECT_URI` in `.env` matches Google Cloud Console settings

### Issue: Database connection fails
**Solution**: Check `DATABASE_URL` in `.env` has correct credentials and host

### Issue: AI/OCR not working
**Solution**: Verify API keys in `.env` are valid and have sufficient credits

## Monitoring & Maintenance

### Logs Location
- Backend: `sudo journalctl -u digicard`
- Nginx: `/var/log/nginx/`
- PostgreSQL: `/var/log/postgresql/`

### Backup Database
```bash
pg_dump -U admin scanner_prod > backup_$(date +%Y%m%d).sql
```

### Update Application
```bash
cd /var/www/digicard
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart digicard
```

## Security Recommendations

1. ✅ Use strong `SECRET_KEY` (minimum 32 random characters)
2. ✅ Restrict `ALLOWED_ORIGINS` to your actual domains
3. ✅ Use HTTPS only (no HTTP)
4. ✅ Keep API keys secure (never commit to git)
5. ✅ Regularly update dependencies
6. ✅ Enable firewall (UFW):
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
7. ✅ Set up automated backups
8. ✅ Monitor logs regularly
9. ✅ Use fail2ban for SSH protection

## Support

For issues or questions:
- Check logs first
- Review this guide
- Contact your system administrator

---

**Last Updated**: 2026-01-08
