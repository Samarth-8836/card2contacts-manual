# Configuration Centralization Summary

## Overview

All configurable values have been centralized for easy production deployment:

1. **Backend**: `backend/config.py` + `.env` file
2. **Frontend**: `frontend/config.js` (with `APP_DOMAIN` substituted at build time)

## IMPORTANT: Domain Configuration

**Single Source of Truth for Domain:**

Set `APP_DOMAIN` in your `.env` file and all URLs will be automatically derived:

```bash
# In .env.production or .env
APP_DOMAIN=https://your-domain.com
```

**Automatically Derived URLs:**
- `FRONTEND_URL`: https://your-domain.com
- `BACKEND_URL`: https://your-domain.com
- `ALLOWED_ORIGINS`: https://your-domain.com
- `REDIRECT_URI`: https://your-domain.com/api/auth/google/callback

**No individual URL configuration needed!** Just set `APP_DOMAIN` once.

## What Changed

### 🎯 Previously Hardcoded Values (Now Configurable)

| Value | Old Location | New Location | Default Value |
|-------|--------------|--------------|---------------|
| URI Domain | Multiple places | `.env` → `APP_DOMAIN` | `app.card2contacts.com` |
| Frontend URL | Hardcoded | Derived from `APP_DOMAIN` | `https://your-domain.com` |
| Backend URL | Hardcoded | Derived from `APP_DOMAIN` | `https://your-domain.com` |
| OAuth Redirect | Hardcoded | Derived from `APP_DOMAIN` | `https://your-domain.com/api/auth/google/callback` |
| CORS Origins | Hardcoded | Derived from `APP_DOMAIN` | `https://your-domain.com` |
| AI Model | `backend/config.py` | `.env` → `LLM_MODEL` | `groq/llama-3.1-8b-instant` |
| OCR Provider | `backend/config.py` | `.env` → `OCR_PROVIDER` | `mistral` |
| Free Scan Limit | Hardcoded as `4` | `.env` → `FREE_TIER_SCAN_LIMIT` | `4` |
| Database URL | Hardcoded in `database.py` | `.env` → `DATABASE_URL` | - |

### 📁 Files Modified

#### Backend Files:
1. **backend/config.py**
   - ✅ Added comprehensive environment configuration
   - ✅ Added `ENVIRONMENT`, `FRONTEND_URL`, `BACKEND_URL`
   - ✅ Added `ALLOWED_ORIGINS` for CORS
   - ✅ Added `FREE_TIER_SCAN_LIMIT` for business logic
   - ✅ Added `DEFAULT_MAX_SUB_ACCOUNTS`
   - ✅ Added future settings for email, rate limiting
   - ✅ Added detailed comments for all options

2. **backend/main.py**
   - ✅ Updated to use `settings.FREE_TIER_SCAN_LIMIT` (3 locations)
   - ✅ Updated CORS to use `settings.ALLOWED_ORIGINS`
   - ✅ All scan limit messages now use the config value

3. **backend/database.py**
   - ✅ Removed hardcoded `DATABASE_URL`
   - ✅ Now imports and uses `settings.DATABASE_URL`

#### Frontend Files:
4. **frontend/config.js** (NEW)
   - ✅ Created centralized frontend configuration
   - ✅ Contains `API_BASE_URL`, `FRONTEND_URL`
   - ✅ Contains feature flags
   - ✅ Contains UI/UX settings (file size limits, allowed types)
   - ✅ Helper functions for logging and feature checks

5. **frontend/index.html**
   - ✅ Added `<script src="config.js"></script>` before `app.js`

6. **frontend/admin.html**
   - ✅ Added `<script src="config.js"></script>` before `admin.js`

#### Configuration Files:
7. **.env.example** (NEW)
   - ✅ Created comprehensive template for production
   - ✅ Includes all configuration options with descriptions
   - ✅ Includes production deployment checklist
   - ✅ Shows all available AI models and OCR providers

8. **PRODUCTION_DEPLOYMENT.md** (NEW)
   - ✅ Complete deployment guide
   - ✅ Step-by-step instructions
   - ✅ Configuration summary
   - ✅ Troubleshooting section

## Quick Reference: What to Change for Production

### 1. Backend Configuration (`.env`)

```bash
# Essential changes:
ENVIRONMENT=production

# DOMAIN CONFIGURATION - Set this ONE variable:
APP_DOMAIN=https://your-domain.com

# All these URLs are automatically derived from APP_DOMAIN:
# - FRONTEND_URL: https://your-domain.com
# - BACKEND_URL: https://your-domain.com
# - ALLOWED_ORIGINS: https://your-domain.com
# - REDIRECT_URI: https://your-domain.com/api/auth/google/callback

DATABASE_URL=postgresql://user:pass@host:5432/db
SECRET_KEY=<generate-random-key>

# Optional changes (adjust for your business):
FREE_TIER_SCAN_LIMIT=4
DEFAULT_MAX_SUB_ACCOUNTS=5

# AI Model changes (pick one):
LLM_MODEL=groq/llama-3.1-8b-instant
# OR
LLM_MODEL=groq/llama-3.3-70b-versatile
# OR
LLM_MODEL=gemini/gemini-flash-lite-latest

# OCR changes:
OCR_PROVIDER=mistral
MISTRAL_MODEL=mistral-ocr-2512
```

### 2. Frontend Configuration (`frontend/config.js`)

```javascript
const CONFIG = {
    ENVIRONMENT: 'production',
    API_BASE_URL: '',  // Same origin, or 'https://api.yourdomain.com' if different
    FRONTEND_URL: '${APP_DOMAIN}',  // Replaced during Docker build with APP_DOMAIN
    ENABLE_CONSOLE_LOGS: false,  // Disable in production
    ENABLE_ERROR_REPORTING: true,  // Enable if using error reporting service
};
```

**Note:** `FRONTEND_URL` is automatically set during Docker build from the `APP_DOMAIN` environment variable. You don't need to manually change this file.

### 3. Google OAuth (Google Cloud Console)

Update authorized redirect URIs to:
```
https://your-production-domain.com/api/auth/google/callback
```

## Benefits of Centralization

### ✅ For Deployment
- Change one file (`.env`) to switch environments
- No need to search through code for hardcoded values
- Easy to maintain separate dev/staging/prod configs

### ✅ For Business Logic
- Change free tier limits from one place
- Switch AI models with one variable
- Adjust rate limits without code changes

### ✅ For Security
- Sensitive values in `.env` (not committed to git)
- Easy to restrict CORS origins in production
- Clear separation of secrets and code

### ✅ For Maintenance
- Clear documentation of all configurable values
- `.env.example` serves as template
- Easy onboarding for new developers

## Additional Configurable Values (Future Use)

These are already in `backend/config.py` for future features:

```python
# Email Configuration
SMTP_HOST: Optional[str] = None
SMTP_PORT: int = 587
SMTP_USER: Optional[str] = None
SMTP_PASSWORD: Optional[str] = None
EMAIL_FROM: Optional[str] = None

# Rate Limiting
RATE_LIMIT_PER_MINUTE: int = 60
BULK_SCAN_MAX_FILES: int = 100
```

## Migration Checklist

If you're updating an existing deployment:

- [ ] Copy `.env.example` to `.env`
- [ ] Fill in all values in `.env`
- [ ] Update `frontend/config.js` with production values
- [ ] Test locally first
- [ ] Update Google OAuth redirect URIs
- [ ] Deploy backend changes
- [ ] Deploy frontend changes (including new `config.js`)
- [ ] Verify all functionality works
- [ ] Monitor logs for any configuration errors

## Code Locations Reference

### Free Tier Scan Limit Usage
Now uses `settings.FREE_TIER_SCAN_LIMIT` in:
- [backend/main.py:413](backend/main.py:413) - Registration message
- [backend/main.py:870](backend/main.py:870) - Expired license scan count
- [backend/main.py:874](backend/main.py:874) - No license scan count
- [backend/main.py:1654](backend/main.py:1654) - Scan limit enforcement

### CORS Origins
- [backend/main.py:111](backend/main.py:111) - CORS middleware configuration

### Database URL
- [backend/database.py:11](backend/database.py:11) - Engine creation

### OAuth Redirect URI
- [backend/config.py:40](backend/config.py:40) - Google OAuth settings

## Troubleshooting

### Issue: Changes in `.env` not taking effect
**Solution**: Restart the backend server
```bash
sudo systemctl restart digicard
# OR if running manually:
# Ctrl+C and restart uvicorn
```

### Issue: Frontend still using old values
**Solution**:
1. Clear browser cache
2. Check `frontend/config.js` was updated
3. Verify `config.js` is loaded before `app.js` in HTML

### Issue: CORS errors after changing `ALLOWED_ORIGINS`
**Solution**:
- Ensure format is correct: comma-separated, no spaces around commas
- Example: `https://domain1.com,https://domain2.com`
- Backend must be restarted after changes

## Summary

All configuration is now centralized! You only need to edit:
- **`.env`** for backend settings
- **`frontend/config.js`** for frontend settings

No more searching through code for hardcoded values! 🎉

---

**Created**: 2026-01-08
