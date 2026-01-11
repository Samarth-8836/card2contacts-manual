# Docker Deployment Guide for DigiCard Enterprise

This guide will help you containerize and deploy DigiCard Enterprise to your production server.

## Prerequisites

- Docker and Docker Compose installed on your production server
- A `.env` file configured with production values (copy from `.env.example`)

## Quick Start

### 1. Configure Environment Variables

Copy the example environment file and update it with your production values:

```bash
cp .env.example .env
```

**Important changes needed for production:**
- `ENVIRONMENT=production`
- `SECRET_KEY` - Generate a strong random string: `openssl rand -hex 32`
- `DATABASE_URL` - Update with production database credentials
- `FRONTEND_URL` and `BACKEND_URL` - Set to your production domain
- `ALLOWED_ORIGINS` - Restrict to your actual domains
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - Production OAuth credentials
- `GEMINI_API_KEY` or `GROQ_API_KEY` - AI provider API key
- `MISTRAL_API_KEY` - OCR provider API key
- SMTP credentials for email

### 2. Build and Start Services

```bash
# Build the containers
docker-compose build

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f
```

### 3. Verify Deployment

- Frontend: http://your-server-ip
- Backend API: http://your-server-ip:8000/docs

## Docker Services

The application consists of three main services:

1. **db** (PostgreSQL 15) - Database
2. **backend** (Python FastAPI) - API server
3. **frontend** (Nginx) - Static file server

## Service Ports

- Frontend (Nginx): 80
- Backend (FastAPI): 8000
- Database (PostgreSQL): 5432

## Useful Docker Commands

```bash
# View running containers
docker-compose ps

# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend

# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# Update and rebuild after code changes
docker-compose up -d --build
```

## Production Tips

### 1. Database Security

Update the database credentials in `docker-compose.yml`:

```yaml
db:
  environment:
    POSTGRES_USER: your_secure_user
    POSTGRES_PASSWORD: your_secure_password
    POSTGRES_DB: scanner_prod
```

Also update the `DATABASE_URL` in `.env` to match.

### 2. SSL/HTTPS

For production, use a reverse proxy like Nginx or Traefik with SSL certificates. Or use cloud load balancers that provide SSL termination.

### 3. Volume Backups

Regularly backup the PostgreSQL volume:

```bash
# Backup database
docker-compose exec db pg_dump -U admin scanner_prod > backup.sql

# Restore database
docker-compose exec -T db psql -U admin scanner_prod < backup.sql
```

### 4. Resource Limits

Add resource limits to `docker-compose.yml` for better resource management:

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs [service_name]

# Check if port is already in use
netstat -tulpn | grep :8000
```

### Database connection issues

- Ensure the database container is healthy: `docker-compose ps`
- Check `DATABASE_URL` in `.env` matches the db service configuration
- Verify network connectivity between containers

### Frontend can't connect to backend

- Verify the nginx proxy configuration in `nginx.conf`
- Check that backend service is running: `docker-compose ps backend`
- Ensure the `/api/` path is correctly proxied

## Updating the Application

When you have code updates:

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

## Initial Setup

After first deployment, you'll need to:

1. Run database migrations (if any)
2. Create the initial admin user
3. Create enterprise admin accounts

Use the helper scripts in the `backend/` directory:

```bash
# Enter backend container
docker-compose exec backend bash

# Create app owner
python create_app_owner.py

# Create enterprise admin
python create_enterprise_admin.py

# Assign distributor role
python assign_distributor_role.py
```

See `ADMIN_SETUP_GUIDE.md` for detailed instructions.
