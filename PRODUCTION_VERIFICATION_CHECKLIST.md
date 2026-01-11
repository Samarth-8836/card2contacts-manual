# Production Verification Checklist

This document verifies that all files are correctly configured for production deployment to `app.card2contacts.com`.

## ✅ Configuration Files

### 1. Frontend Configuration
- **File:** `frontend/config.js`
- **Status:** ✅ VERIFIED
- **Values:**
  - `ENVIRONMENT: 'production'` ✅
  - `FRONTEND_URL: 'https://app.card2contacts.com'` ✅
  - `API_BASE_URL: ''` (empty for relative URLs) ✅
  - `ENABLE_CONSOLE_LOGS: false` ✅
  - `ENABLE_ERROR_REPORTING: true` ✅

### 2. Backend Configuration
- **File:** `backend/config.py`
- **Status:** ✅ VERIFIED
- **Values:**
  - `ENVIRONMENT: 'production'` ✅
  - `FRONTEND_URL: 'https://app.card2contacts.com'` ✅
  - `BACKEND_URL: 'https://app.card2contacts.com'` ✅
  - `ALLOWED_ORIGINS: 'https://app.card2contacts.com'` ✅
  - `REDIRECT_URI: 'https://app.card2contacts.com/api/auth/google/callback'` ✅
  - `extra: "ignore"` (pydantic setting) ✅

### 3. Nginx Configuration
- **File:** `nginx-production.conf`
- **Status:** ✅ VERIFIED
- **Routing:**
  - `/` → Serves `index.html` ✅
  - `/admin.html` → Serves `admin.html` ✅
  - `/api/` → Proxies to backend ✅
  - Static files cached for 1 year ✅
- **SSL:**
  - Certificate path: `/etc/nginx/ssl/fullchain.pem` ✅
  - Key path: `/etc/nginx/ssl/privkey.pem` ✅
  - Protocols: TLSv1.2, TLSv1.3 ✅
  - HTTP → HTTPS redirect ✅

### 4. Docker Compose
- **File:** `docker-compose.production.yml`
- **Status:** ✅ VERIFIED
- **Database:**
  - Port binding: `127.0.0.1:5432:5432` (localhost only) ✅
  - Environment variable: `${POSTGRES_PASSWORD}` ✅
  - Health check configured ✅
  - Volume mounted for backups ✅
- **Backend:**
  - Uses `Dockerfile` ✅
  - `.env.production` mounted ✅
  - Exposes port 8000 internally ✅
  - Database URL uses `${POSTGRES_PASSWORD}` ✅
- **Frontend:**
  - Uses `Dockerfile.frontend` ✅
  - Build arg `NGINX_CONF: nginx-production.conf` ✅
  - Ports 80 and 443 exposed ✅
  - SSL certificates volume mounted ✅

### 5. Dockerfiles

#### Backend Dockerfile
- **File:** `Dockerfile`
- **Status:** ✅ VERIFIED
- **Configuration:**
  - Base: `python:3.10-slim` ✅
  - System dependencies: gcc, libpq-dev ✅
  - Copies requirements.txt and backend/ ✅
  - Exposes port 8000 ✅
  - Runs uvicorn on 0.0.0.0:8000 ✅

#### Frontend Dockerfile
- **File:** `Dockerfile.frontend`
- **Status:** ✅ VERIFIED
- **Configuration:**
  - Base: `nginx:alpine` ✅
  - Copies frontend/ to /usr/share/nginx/html/ ✅
  - Supports NGINX_CONF build arg ✅
  - Copies specified nginx config ✅
  - Exposes ports 80 and 443 ✅

### 6. Environment File
- **File:** `.env.production`
- **Status:** ✅ VERIFIED (template created)
- **Required User Updates:**
  - `POSTGRES_PASSWORD` (must generate with openssl) ⚠️
  - `SECRET_KEY` (must generate with openssl) ⚠️
  - `GOOGLE_CLIENT_ID` (from Google Cloud Console) ⚠️
  - `GOOGLE_CLIENT_SECRET` (from Google Cloud Console) ⚠️
  - `GROQ_API_KEY` (from Groq console) ⚠️
  - `MISTRAL_API_KEY` (from Mistral console) ⚠️
  - SMTP credentials (from Hostinger) ⚠️
- **Default Values:**
  - `ENVIRONMENT=production` ✅
  - `FRONTEND_URL=https://app.card2contacts.com` ✅
  - `BACKEND_URL=https://app.card2contacts.com` ✅
  - `ALLOWED_ORIGINS=https://app.card2contacts.com` ✅
  - `REDIRECT_URI=https://app.card2contacts.com/api/auth/google/callback` ✅
  - Database pool settings configured ✅

### 7. Frontend Files
- **Files:** `frontend/index.html`, `frontend/admin.html`
- **Status:** ✅ VERIFIED
- Both HTML files exist and will be served by Nginx ✅

### 8. Helper Scripts
- **File:** `backup.sh`
- **Status:** ✅ VERIFIED
- Automated database backup script created ✅
- Keeps only last 7 days ✅
- Compresses backups ✅

### 9. Admin Setup Script
- **File:** `backend/create_app_owner.py`
- **Status:** ✅ VERIFIED
- Uses `settings.FRONTEND_URL` for admin URL ✅
- No hardcoded localhost references ✅

## ✅ File Locations

### Files to Deploy
```
/opt/digicard/
├── Dockerfile                          ✅
├── Dockerfile.frontend                 ✅
├── nginx-production.conf               ✅
├── nginx.conf (development only)       ✅
├── docker-compose.production.yml        ✅
├── .env.production (template)          ✅
├── .gitignore                         ✅
├── .dockerignore                       ✅
├── backup.sh                          ✅
├── backend/                           ✅
│   ├── main.py                        ✅
│   ├── config.py                      ✅
│   ├── database.py                    ✅
│   ├── create_app_owner.py            ✅
│   └── ... (other backend files)
└── frontend/                          ✅
    ├── index.html                     ✅
    ├── admin.html                     ✅
    ├── config.js                     ✅
    ├── app.js                        ✅
    ├── admin.js                      ✅
    └── style.css                     ✅
```

### Files Created on Server (Not Committed)
```
/opt/digicard/
├── .env.production.local              (secrets - DON'T COMMIT) ⚠️
├── certs/                            (SSL certificates - DON'T COMMIT) ⚠️
│   ├── fullchain.pem
│   └── privkey.pem
└── backups/                          (database backups - DON'T COMMIT) ⚠️
    └── db_backup_*.sql.gz
```

## ✅ No Remaining sslip.io References

All sslip.io references have been removed or will be overridden by environment variables:

- `backend/config.py` - Now defaults to `https://app.card2contacts.com` ✅
- `frontend/config.js` - Updated to `https://app.card2contacts.com` ✅
- `.env.production` - All URLs set to `https://app.card2contacts.com` ✅

## ⚠️ Required Before Deployment

### 1. Generate Secure Secrets
```bash
# Generate database password
openssl rand -base64 32

# Generate secret key
openssl rand -hex 32
```

### 2. Create Production Environment File
```bash
cp .env.production .env.production.local
# Edit .env.production.local and update:
# - POSTGRES_PASSWORD (use generated password)
# - SECRET_KEY (use generated secret)
# - GOOGLE_CLIENT_ID
# - GOOGLE_CLIENT_SECRET
# - GROQ_API_KEY
# - MISTRAL_API_KEY
# - SMTP credentials
```

### 3. Obtain SSL Certificates
```bash
sudo certbot certonly --standalone -d app.card2contacts.com
sudo mkdir -p /opt/digicard/certs
sudo cp /etc/letsencrypt/live/app.card2contacts.com/fullchain.pem /opt/digicard/certs/
sudo cp /etc/letsencrypt/live/app.card2contacts.com/privkey.pem /opt/digicard/certs/
sudo chown $USER:$USER /opt/digicard/certs/*
```

### 4. Configure Google OAuth
- Go to Google Cloud Console
- Create OAuth 2.0 client ID
- Authorized JavaScript origins: `https://app.card2contacts.com`
- Authorized redirect URI: `https://app.card2contacts.com/api/auth/google/callback`
- Add to `.env.production.local`

### 5. Obtain API Keys
- Groq: https://console.groq.com/keys
- Mistral: https://console.mistral.ai/api-keys
- Add to `.env.production.local`

## ✅ Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Ubuntu Server                            │
│                   app.card2contacts.com                       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  Port 80/443                               │
│  │   Frontend   │  (Nginx + SSL)                              │
│  │   Container  │  - index.html at /                           │
│  │              │  - admin.html at /admin.html                 │
│  │              │  - /api/* → backend container                │
│  └──────────────┘                                            │
│         │                                                     │
│         ▼                                                     │
│  ┌──────────────┐  Port 8000 (internal)                       │
│  │   Backend    │  (FastAPI)                                  │
│  │   Container  │  - API endpoints                           │
│  └──────────────┘                                            │
│         │                                                     │
│         ▼                                                     │
│  ┌──────────────┐  Port 5432 (localhost only)                 │
│  │  Database    │  (PostgreSQL 15)                           │
│  │   Container  │  - User data                                │
│  └──────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
```

## ✅ Production Security

### Network Security
- Database only accessible from localhost (`127.0.0.1:5432`) ✅
- Backend only accessible via frontend proxy ✅
- Frontend exposed on ports 80 and 443 ✅

### Application Security
- CORS restricted to `https://app.card2contacts.com` ✅
- SSL/TLS enforced (HTTP → HTTPS redirect) ✅
- Strong passwords required for database and secrets ⚠️
- Secrets stored in `.env.production.local` (not committed) ✅
- Environment variable: `ENVIRONMENT=production` ✅

### File Security
- `.env.production.local` in `.gitignore` ✅
- `certs/` directory in `.gitignore` ✅
- `backups/` directory in `.gitignore` ✅
- `.dockerignore` excludes unnecessary files ✅

## ✅ Production URLs

After deployment, these URLs will work:

- **Main Application:** `https://app.card2contacts.com/`
- **Admin Panel:** `https://app.card2contacts.com/admin.html`
- **API Documentation:** `https://app.card2contacts.com/api/docs`
- **API Endpoints:** `https://app.card2contacts.com/api/*`
- **Google OAuth Callback:** `https://app.card2contacts.com/api/auth/google/callback`

## ✅ API Proxy Configuration

Nginx will proxy API requests as follows:

```
Request: https://app.card2contacts.com/api/scan
Nginx: Proxies to http://backend:8000/api/scan
Backend: Handles the request and returns response
Response: Sent back to client via Nginx
```

## ✅ Final Deployment Steps

1. **Server Setup** (as per UBUNTU_DEPLOYMENT_GUIDE.md)
   - Install Docker and Docker Compose
   - Clone repository
   - Set up SSL certificates

2. **Configure Secrets** (as per above)
   - Generate passwords
   - Create `.env.production.local`
   - Add all API keys and credentials

3. **Deploy**
   ```bash
   docker-compose -f docker-compose.production.yml build
   docker-compose -f docker-compose.production.yml up -d
   ```

4. **Initial Setup**
   ```bash
   docker-compose -f docker-compose.production.yml exec backend python create_app_owner.py
   ```

5. **Verify**
   - Access https://app.card2contacts.com
   - Access https://app.card2contacts.com/admin.html
   - Test Google OAuth
   - Test file upload and scanning

## ✅ Summary

All files are verified and ready for production deployment. The only remaining work is:

1. Generate secrets (passwords, keys) ⚠️
2. Create `.env.production.local` with production values ⚠️
3. Obtain SSL certificates ⚠️
4. Configure Google OAuth ⚠️
5. Deploy to Ubuntu server ⚠️

After completing these steps, the application will be fully functional in production at `https://app.card2contacts.com`.
