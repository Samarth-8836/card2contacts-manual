# Production Changes Required Checklist

This document lists all changes needed before deploying to production on app.card2contacts.com.

## Files That Need Changes

### 1. ✅ frontend/config.js
**Status:** UPDATED
- Changed `ENVIRONMENT` from 'development' to 'production'
- Changed `FRONTEND_URL` from 'https://192.168.29.234.sslip.io:8000' to 'https://app.card2contacts.com'
- Changed `ENABLE_CONSOLE_LOGS` from true to false
- Changed `ENABLE_ERROR_REPORTING` from false to true
- `API_BASE_URL` remains empty (will use same origin)

### 2. ⚠️ backend/config.py
**Status:** NEEDS MANUAL UPDATE
Currently has hardcoded values that should be overridden by .env
- Default values contain sslip.io URLs
- These will be overridden by .env.production file
- **Action:** No code changes needed, but ensure .env.production.local is created

### 3. ✅ .env.production
**Status:** CREATED
Created new production environment file with:
- ENVIRONMENT=production
- FRONTEND_URL=https://app.card2contacts.com
- BACKEND_URL=https://app.card2contacts.com
- ALLOWED_ORIGINS=https://app.card2contacts.com
- REDIRECT_URI=https://app.card2contacts.com/api/auth/google/callback
- All other production-ready defaults

### 4. ✅ nginx-production.conf
**Status:** CREATED
Created production Nginx config with:
- SSL/TLS enabled on port 443
- HTTP to HTTPS redirect on port 80
- index.html served at root path /
- admin.html served at /admin.html
- API proxy to backend
- Static file caching
- Proper SSL configuration

### 5. ✅ docker-compose.production.yml
**Status:** CREATED
Created production docker-compose with:
- Security hardening (database only on localhost)
- SSL certificate volume mount
- Separate production environment file
- Health checks
- Proper networking
- Volume for backups

### 6. ✅ Dockerfile
**Status:** CREATED
Backend Dockerfile created with:
- Python 3.10 slim base image
- System dependencies for PostgreSQL
- Copies requirements.txt and backend code
- Exposes port 8000
- Runs uvicorn server

### 7. ✅ Dockerfile.frontend
**Status:** CREATED
Frontend Dockerfile created with:
- Nginx Alpine base
- Copies frontend files
- Uses nginx configuration
- Exposes port 80

### 8. ✅ .dockerignore
**Status:** CREATED
Excludes unnecessary files from Docker builds

## Manual Configuration Required

### Before Deployment (Must Do):

1. **Generate Strong Passwords**
   ```bash
   openssl rand -base64 32  # For database
   openssl rand -hex 32     # For SECRET_KEY
   ```

2. **Create .env.production.local**
   ```bash
   cp .env.production .env.production.local
   # Edit and update:
   # - POSTGRES_PASSWORD (use generated password)
   # - SECRET_KEY (use generated secret)
   # - GOOGLE_CLIENT_ID (from Google Cloud Console)
   # - GOOGLE_CLIENT_SECRET (from Google Cloud Console)
   # - GROQ_API_KEY
   # - MISTRAL_API_KEY
   # - SMTP_USER
   # - SMTP_PASSWORD
   ```

3. **Obtain SSL Certificates**
   ```bash
   sudo certbot certonly --standalone -d app.card2contacts.com
   sudo cp /etc/letsencrypt/live/app.card2contacts.com/fullchain.pem /opt/digicard/certs/
   sudo cp /etc/letsencrypt/live/app.card2contacts.com/privkey.pem /opt/digicard/certs/
   ```

4. **Configure Google OAuth**
   - Go to Google Cloud Console
   - Create OAuth 2.0 credentials for app.card2contacts.com
   - Set authorized redirect URI: https://app.card2contacts.com/api/auth/google/callback
   - Copy client ID and secret to .env.production.local

5. **Obtain API Keys**
   - Groq API Key: https://console.groq.com/keys
   - Mistral API Key: https://console.mistral.ai/api-keys
   - Add to .env.production.local

6. **Update docker-compose.production.yml**
   - Update database password reference to use ${POSTGRES_PASSWORD}

## Files Containing sslip.io References (Auto-Handled)

These files contain sslip.io references but are automatically overridden by .env.production:

1. **backend/config.py** - Lines 17, 18, 40
   - These are default values
   - Will be overridden by .env.production.local
   - No action needed

2. **.env** (development file)
   - Contains development configuration
   - Not used in production deployment
   - No action needed

3. **frontend/config.js**
   - Already updated to production values
   - No action needed

## Security Changes for Production

### 1. Database Access
- Changed from exposing port 5432 to binding to 127.0.0.1:5432 only
- Only accessible from localhost, not from external network

### 2. SSL/TLS
- Full SSL configuration in nginx-production.conf
- Auto-renewal setup with cron job
- Only HTTPS allowed (HTTP redirects to HTTPS)

### 3. CORS
- ALLOWED_ORIGINS restricted to https://app.card2contacts.com
- Removed wildcard "*"

### 4. Environment
- ENVIRONMENT set to "production"
- Console logs disabled in frontend
- Error reporting enabled

### 5. Secret Management
- Strong random passwords required
- Separate .env.production.local file (not committed to git)
- All secrets properly managed

## Deployment Verification Checklist

After deployment, verify:

- [ ] Frontend loads at https://app.card2contacts.com
- [ ] Admin panel loads at https://app.card2contacts.com/admin.html
- [ ] API accessible at https://app.card2contacts.com/api/docs
- [ ] SSL certificate is valid
- [ ] Google OAuth works
- [ ] File upload and scanning works
- [ ] Database is not accessible externally
- [ ] Logs show no errors
- [ ] Backups are scheduled
- [ ] SSL auto-renewal is configured

## Additional Files Created

1. **UBUNTU_DEPLOYMENT_GUIDE.md** - Step-by-step deployment instructions
2. **nginx-production.conf** - Production Nginx configuration
3. **docker-compose.production.yml** - Production Docker Compose file
4. **.env.production** - Production environment template
5. **Dockerfile** - Backend container definition
6. **Dockerfile.frontend** - Frontend container definition
7. **.dockerignore** - Docker build exclusions

## Summary

**Files Modified:**
- frontend/config.js ✅

**Files Created:**
- Dockerfile ✅
- Dockerfile.frontend ✅
- nginx-production.conf ✅
- docker-compose.production.yml ✅
- .env.production ✅
- .dockerignore ✅
- UBUNTU_DEPLOYMENT_GUIDE.md ✅
- PRODUCTION_CHANGES_CHECKLIST.md ✅ (this file)

**Files Not Modified (Auto-Handled):**
- backend/config.py (default values overridden by .env)
- .env (development file, not used in production)

**Manual Setup Required:**
- Generate passwords and secret keys
- Create .env.production.local with production values
- Obtain SSL certificates
- Configure Google OAuth
- Obtain API keys
- Set up monitoring and backups

## Next Steps

Follow the UBUNTU_DEPLOYMENT_GUIDE.md for complete deployment instructions.
