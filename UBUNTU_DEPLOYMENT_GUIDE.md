# Production Deployment Guide - Ubuntu Server

This guide provides step-by-step instructions to deploy DigiCard Enterprise to an Ubuntu server.

## Prerequisites

- Ubuntu 20.04 LTS or 22.04 LTS
- Domain name pointing to your server (e.g., app.card2contacts.com or dev.card2contacts.com)
- Root or sudo access
- At least 2GB RAM and 20GB disk space
- Valid SSL certificate for your domain

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

# Get certificate (standalone mode) - replace your-domain.com with your actual domain
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates to application directory - replace your-domain.com with your actual domain
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /opt/digicard/certs/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem /opt/digicard/certs/

# Set permissions
sudo chown -R $USER:$USER /opt/digicard/certs/
sudo chmod 644 /opt/digicard/certs/*
```

### 4.3 Set Up Auto-Renewal

```bash
sudo crontab -e
```

Add this line at the end (replace your-domain.com with your actual domain):

```
0 3 * * * certbot renew --quiet --post-hook "cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /opt/digicard/certs/ && cp /etc/letsencrypt/live/your-domain.com/privkey.pem /opt/digicard/certs/ && docker-compose -f /opt/digicard/docker-compose.production.yml restart frontend"
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

IMPORTANT - HAVE BOTH FILES (.env.production and .env.production.local) UPDATED TO THE SAME VALUES SINCE BOTH ARE BEING USED SOMEWHERE

```bash
cd /opt/digicard
cp .env.production .env.production.local
nano .env.production.local
```

**IMPORTANT**: Set your domain using the `APP_DOMAIN` variable. All URLs will be automatically derived from this single value:

```env
# Domain Configuration - SINGLE SOURCE OF TRUTH
APP_DOMAIN=https://your-domain.com

# Examples:
# APP_DOMAIN=https://app.card2contacts.com
# APP_DOMAIN=https://dev.card2contacts.com

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

IMPORTANT - if we only allow 80 and 443 then we will not be able to SSH into the server again. Do not enable firewall or if strictly needed then allow ssh with it otherwise we will be locked out.
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

Replace `your-domain.com` with the domain you set in `APP_DOMAIN`:

- Main App: https://your-domain.com
- Admin Panel: https://your-domain.com/admin.html
- API Documentation: https://your-domain.com/api/docs

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
# Renew certificate (replace your-domain.com with your actual domain)
sudo certbot renew --force-renewal

# Copy new certificates (replace your-domain.com with your actual domain)
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /opt/digicard/certs/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem /opt/digicard/certs/

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

## Database Backup and Restore Operations

### Restarting Server Services

To restart all services on the server:

```bash
# Stop all services
docker-compose -f docker-compose.production.yml down

# Start all services
docker-compose -f docker-compose.production.yml up -d
```

### Restoring Database to Server

Use the PowerShell restore script to restore a database backup from your local Windows machine to any server (production, development, or testing).

#### Prerequisites
- Windows PowerShell with ExecutionPolicy Bypass
- SSH access to the target server
- SSH private key file
- Backup file stored locally at `D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\`

#### Restore Command

Run from Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\Code Projects\c2c-demo hosted\DigiCard-Enterprise\restore-db.ps1"
```

#### Sample Restore Execution with Logs

```
PS C:\WINDOWS\system32> powershell -ExecutionPolicy Bypass -File "D:\Code Projects\c2c-demo hosted\DigiCard-Enterprise\restore-db.ps1"
[2026-01-21 14:50:42] [INFO] ==========================================
[2026-01-21 14:50:42] [INFO] Card2Contacts Database Restore Script
[2026-01-21 14:50:42] [INFO] ==========================================
[2026-01-21 14:50:42] [INFO]
[2026-01-21 14:50:42] [INFO] Step 1: SSH Key Configuration
Enter SSH private key path : : D:\SECURE-DO-NOT-DELETE\Card2Contacts-dev-server-access\card2contacts - dev server.pem
[2026-01-21 14:50:54] [SUCCESS] SSH key file verified: D:\SECURE-DO-NOT-DELETE\Card2Contacts-dev-server-access\card2contacts - dev server.pem
[2026-01-21 14:50:54] [INFO] Fixing SSH key permissions...
[2026-01-21 14:50:54] [INFO] SSH key path to fix: D:\SECURE-DO-NOT-DELETE\Card2Contacts-dev-server-access\card2contacts - dev server.pem
[2026-01-21 14:50:54] [INFO] Resolved absolute path: D:\SECURE-DO-NOT-DELETE\Card2Contacts-dev-server-access\card2contacts - dev server.pem
[2026-01-21 14:50:54] [SUCCESS] SSH key permissions fixed successfully
[2026-01-21 14:50:54] [INFO]
[2026-01-21 14:50:54] [INFO] Step 2: Target Server Configuration
Enter target server IP address : : 13.235.84.168
Enter SSH username [ubuntu]: :
Enter docker-compose file path [/opt/digicard/docker-compose.production.yml]: :
Enter project directory [/opt/digicard]: :
Enter POSTGRES_PASSWORD : : ***************
[2026-01-21 14:51:10] [INFO] Server configuration collected
[2026-01-21 14:51:10] [INFO]
[2026-01-21 14:51:10] [INFO] Step 3: Select Backup File

Available backup files:
  1. db_backup_20260121_075156.sql.gz (4.52 KB) - 2026-01-21 13:22:02
  2. db_backup_20260121_055214.sql.gz (4.52 KB) - 2026-01-21 11:22:19
  3. db_backup_20260121_054520.sql.gz (4.52 KB) - 2026-01-21 11:15:25

Select backup file (1-3, or 'q' to quit) : : 1
[2026-01-21 14:51:14] [INFO] Selected backup: db_backup_20260121_075156.sql.gz (4.52 KB)
[2026-01-21 14:51:14] [INFO]
[2026-01-21 14:51:14] [INFO] Step 4: Confirmation

========================================
Restore Configuration Summary:
========================================
  Target Server: 13.235.84.168
  SSH Username: ubuntu
  Project Dir: /opt/digicard
  Backup File: db_backup_20260121_075156.sql.gz (4.52 KB)
========================================

Type 'CONFIRM' to proceed or 'CANCEL' to abort : : CONFIRM
[2026-01-21 14:51:17] [INFO] User confirmed restore operation
[2026-01-21 14:51:17] [INFO]
[2026-01-21 14:51:17] [INFO] Step 5: Creating Safety Backup
[2026-01-21 14:51:17] [INFO] Executing SSH command: cd /opt/digicard && sudo chmod +x backup.sh && sudo ./backup.sh
[2026-01-21 14:51:18] [SUCCESS] Safety backup created: db_backup_20260121_092118.sql.gz
[2026-01-21 14:51:18] [INFO]
[2026-01-21 14:51:18] [INFO] Step 6: Stopping Services
[2026-01-21 14:51:18] [INFO] Stopping container: scanner_frontend
[2026-01-21 14:51:18] [INFO] Executing SSH command: sudo docker stop scanner_frontend
[2026-01-21 14:51:19] [INFO] Waiting 30 seconds for container to stop...
[2026-01-21 14:51:49] [INFO] Executing SSH command: docker ps --filter name=scanner_frontend --format '{{.Status}}'
[2026-01-21 14:51:49] [SUCCESS] Container scanner_frontend stopped successfully
[2026-01-21 14:51:49] [INFO] Stopping container: scanner_backend
[2026-01-21 14:51:49] [INFO] Executing SSH command: sudo docker stop scanner_backend
[2026-01-21 14:51:51] [INFO] Waiting 30 seconds for container to stop...
[2026-01-21 14:52:21] [INFO] Executing SSH command: docker ps --filter name=scanner_backend --format '{{.Status}}'
[2026-01-21 14:52:21] [SUCCESS] Container scanner_backend stopped successfully
[2026-01-21 14:52:21] [INFO]
[2026-01-21 14:52:21] [INFO] Step 7: Uploading Backup File
[2026-01-21 14:52:21] [INFO] Uploading to temporary location (/tmp) to avoid permission errors...
[2026-01-21 14:52:21] [INFO] Uploading file: D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\db_backup_20260121_075156.sql.gz -> ubuntu@13.235.84.168:/tmp
[2026-01-21 14:52:22] [SUCCESS] File uploaded successfully
[2026-01-21 14:52:22] [INFO] File uploaded to /tmp successfully. Moving to final destination...
[2026-01-21 14:52:22] [INFO] Executing SSH command: sudo mkdir -p /opt/digicard/backups && sudo mv /tmp/db_backup_20260121_075156.sql.gz /opt/digicard/backups/db_backup_20260121_075156.sql.gz
[2026-01-21 14:52:22] [SUCCESS] File moved to /opt/digicard/backups successfully
[2026-01-21 14:52:22] [INFO]
[2026-01-21 14:52:22] [INFO] Step 8: Decompressing Backup File
[2026-01-21 14:52:22] [INFO] Executing SSH command: cd /opt/digicard/backups && sudo gunzip -k db_backup_20260121_075156.sql.gz
[2026-01-21 14:52:23] [SUCCESS] Backup decompressed: db_backup_20260121_075156.sql
[2026-01-21 14:52:23] [INFO]
[2026-01-21 14:52:23] [INFO] Step 9: Restoring Database
[2026-01-21 14:52:23] [INFO] Cleaning existing database (Wiping all data)...
[2026-01-21 14:52:23] [INFO] Executing SSH command: cd /opt/digicard && sudo docker-compose -f /opt/digicard/docker-compose.production.yml exec -T db psql -U admin -d scanner_prod -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
NOTICE:  drop cascades to 9 other objects
DETAIL:  drop cascades to table license
drop cascades to table distributor
drop cascades to table appowner
drop cascades to table otprecord
drop cascades to table "user"
drop cascades to table enterpriseadmin
drop cascades to table distributorlicense
drop cascades to table distributorpurchase
drop cascades to table subaccount
[2026-01-21 14:52:24] [SUCCESS] Database wiped successfully
[2026-01-21 14:52:24] [INFO] Executing restore command (this may take a few minutes)...
[2026-01-21 14:52:24] [INFO] Executing SSH command: cd /opt/digicard && sudo docker-compose -f /opt/digicard/docker-compose.production.yml exec -T db psql -U admin -d scanner_prod < /opt/digicard/backups/db_backup_20260121_075156.sql
[2026-01-21 14:52:24] [SUCCESS] Database restored successfully
[2026-01-21 14:52:24] [INFO]
[2026-01-21 14:52:24] [INFO] Step 10: Starting Services
[2026-01-21 14:52:24] [INFO] Starting container: scanner_backend
[2026-01-21 14:52:24] [INFO] Executing SSH command: sudo docker start scanner_backend
[2026-01-21 14:52:25] [INFO] Waiting 30 seconds for container to be ready...
[2026-01-21 14:52:55] [INFO] Executing SSH command: docker ps --filter name=scanner_backend --format '{{.Status}}'
[2026-01-21 14:52:55] [SUCCESS] Container scanner_backend started successfully. Status: Up 30 seconds
[2026-01-21 14:52:55] [INFO] Starting container: scanner_frontend
[2026-01-21 14:52:55] [INFO] Executing SSH command: sudo docker start scanner_frontend
[2026-01-21 14:52:57] [INFO] Waiting 10 seconds for container to be ready...
[2026-01-21 14:53:07] [INFO] Executing SSH command: docker ps --filter name=scanner_frontend --format '{{.Status}}'
[2026-01-21 14:53:08] [SUCCESS] Container scanner_frontend started successfully. Status: Up 10 seconds
[2026-01-21 14:53:08] [INFO]
[2026-01-21 14:53:08] [INFO] Step 11: Cleanup
[2026-01-21 14:53:08] [INFO] Executing SSH command: cd /opt/digicard/backups && sudo rm -f db_backup_20260121_075156.sql.gz db_backup_20260121_075156.sql
[2026-01-21 14:53:08] [SUCCESS] Cleanup completed successfully
[2026-01-21 14:53:08] [INFO]
[2026-01-21 14:53:08] [INFO] ==========================================
[2026-01-21 14:53:08] [INFO] RESTORE SUMMARY
[2026-01-21 14:53:08] [INFO] ==========================================
[2026-01-21 14:53:08] [INFO]   Target Server: 13.235.84.168
[2026-01-21 14:53:08] [INFO]   Backup File: db_backup_20260121_075156.sql.gz (4.52 KB)
[2026-01-21 14:53:08] [INFO]   Safety Backup: db_backup_20260121_092118.sql.gz
[2026-01-21 14:53:08] [INFO]   Services: Stopped and Restarted
[2026-01-21 14:53:08] [INFO]   Status: SUCCESS
[2026-01-21 14:53:08] [INFO] ==========================================
[2026-01-21 14:53:08] [INFO]
[2026-01-21 14:53:08] [INFO] Log file: D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\restore-logs\restore-20260121-145042.log
[2026-01-21 14:53:08] [INFO] ==========================================

Restore completed successfully!
Log file: D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\restore-logs\restore-20260121-145042.log
```

#### Restore Process Details

The restore script performs the following steps:

1. **SSH Key Configuration** - Asks for SSH private key path and fixes permissions automatically
2. **Target Server Configuration** - Collects server IP, SSH username, docker-compose path, project directory, and PostgreSQL password
3. **Backup File Selection** - Lists all available backups from local directory and allows selection
4. **Confirmation** - Shows summary and requires "CONFIRM" to proceed
5. **Safety Backup** - Creates a fresh backup of the current database before restoring
6. **Stop Services** - Stops frontend (60s wait), then backend (30s wait)
7. **Upload Backup** - Uploads selected backup file to server
8. **Decompress Backup** - Extracts the compressed SQL file
9. **Restore Database** - Wipes existing data and restores from backup
10. **Start Services** - Starts backend (30s wait), then frontend (10s wait)
11. **Cleanup** - Removes uploaded backup files from server
12. **Summary** - Logs all operations and provides summary

#### Important Notes

- **Safety Backup**: Always created before restoring - keeps current state
- **Database Wipe**: Existing data is completely replaced with backup data
- **Service Downtime**: Expect ~2 minutes of downtime during restore
- **7-Day Retention**: All backups (including safety backups) follow 7-day retention
- **Automatic Permission Fix**: Script fixes SSH key permissions automatically
- **Logs**: Detailed logs stored in `D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\restore-logs\`

### Taking Database Backups

#### Automated Daily Backup (Windows Task Scheduler)

The backup script is configured to run automatically every day at 2:00 AM IST on your local Windows machine.

**Automatic Backup Command:**
```powershell
powershell -ExecutionPolicy Bypass -File "D:\Code Projects\c2c-demo hosted\DigiCard-Enterprise\backup-local.ps1"
```

#### Manual Backup (Any Time)

Run the backup script manually from Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\Code Projects\c2c-demo hosted\DigiCard-Enterprise\backup-local.ps1"
```

#### Sample Backup Execution with Logs

```
PS C:\WINDOWS\system32> powershell -ExecutionPolicy Bypass -File "D:\Code Projects\c2c-demo hosted\DigiCard-Enterprise\backup-local.ps1"
[2026-01-21 14:57:02] [INFO] ==========================================
[2026-01-21 14:57:02] [INFO] Card2Contacts Database Backup Script Started
[2026-01-21 14:57:02] [INFO] ==========================================
[2026-01-21 14:57:02] [INFO] Creating directories...
[2026-01-21 14:57:02] [INFO] Directories verified/created
[2026-01-21 14:57:02] [INFO] Running pre-flight checks...
[2026-01-21 14:57:02] [INFO] SSH key file verified: D:\SECURE-DO-NOT-DELETE\Card2Contacts-app-server-access\card2contacts - app server.pem
[2026-01-21 14:57:02] [INFO] Fixing SSH key permissions...
[2026-01-21 14:57:02] [INFO] SSH key path to fix: D:\SECURE-DO-NOT-DELETE\Card2Contacts-app-server-access\card2contacts - app server.pem
[2026-01-21 14:57:02] [INFO] Resolved absolute path: D:\SECURE-DO-NOT-DELETE\Card2Contacts-app-server-access\card2contacts - app server.pem
[2026-01-21 14:57:02] [SUCCESS] SSH key permissions fixed successfully
[2026-01-21 14:57:02] [INFO] OpenSSH client verified
[2026-01-21 14:57:02] [INFO] Triggering remote backup on server...
[2026-01-21 14:57:02] [INFO] Command: cd /opt/digicard && sudo ./backup.sh
[2026-01-21 14:57:03] [INFO] Backup command output:
[2026-01-21 14:57:03] [INFO] [Wed Jan 21 09:27:03 UTC 2026] Starting database backup... [Wed Jan 21 09:27:03 UTC 2026] Backup completed: db_backup_20260121_092703.sql.gz Backup directory size: 52K    /opt/digicard/backups Recent backups: total 48K -rw-r--r-- 1 root root 4.3K Jan 21 05:03 db_backup_20260121_050342.sql.gz -rw-r--r-- 1 root root 4.6K Jan 21 05:45 db_backup_20260121_054520.sql.gz -rw-r--r-- 1 root root 4.6K Jan 21 05:52 db_backup_20260121_055214.sql.gz -rw-r--r-- 1 root root 4.6K Jan 21 07:51 db_backup_20260121_075156.sql.gz -rw-r--r-- 1 root root 4.6K Jan 21 09:26 db_backup_20260121_092619.sql.gz -rw-r--r-- 1 root root 4.6K Jan 21 09:27 db_backup_20260121_092703.sql.gz
[2026-01-21 14:57:03] [INFO] Remote backup completed successfully: db_backup_20260121_092703.sql.gz
[2026-01-21 14:57:03] [INFO] Waiting 5 seconds for file system sync...
[2026-01-21 14:57:08] [INFO] Verifying backup file exists on remote server...
[2026-01-21 14:57:09] [INFO] Backup file verified on remote server
[2026-01-21 14:57:09] [INFO] Downloading backup from remote server...
[2026-01-21 14:57:09] [INFO] SCP command: scp -i "D:\SECURE-DO-NOT-DELETE\Card2Contacts-app-server-access\card2contacts - app server.pem" ubuntu@43.205.99.125:/opt/digicard/backups/db_backup_20260121_092703.sql.gz "D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\db_backup_20260121_092703.sql.gz"
db_backup_20260121_092703.sql.gz                                                      100% 4628   173.8KB/s   00:00
[2026-01-21 14:57:09] [INFO] Verifying downloaded file...
[2026-01-21 14:57:09] [INFO] Downloaded: db_backup_20260121_092703.sql.gz (4.52 KB)
[2026-01-21 14:57:09] [INFO] Cleaning up old local backups (older than 7 days)...
[2026-01-21 14:57:09] [INFO] No old backups to clean up
[2026-01-21 14:57:09] [INFO] ==========================================
[2026-01-21 14:57:09] [INFO] Backup Summary:
[2026-01-21 14:57:09] [INFO]   - Downloaded: db_backup_20260121_092703.sql.gz
[2026-01-21 14:57:09] [INFO]   - Size: 4.52 KB
[2026-01-21 14:57:09] [INFO]   - Location: D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\db_backup_20260121_092703.sql.gz
[2026-01-21 14:57:09] [INFO]   - Cleaned: 0 old backup(s)
[2026-01-21 14:57:09] [INFO] ==========================================
[2026-01-21 14:57:09] [INFO] Script completed successfully
[2026-01-21 14:57:09] [INFO] ==========================================
```

#### Backup Process Details

The backup script performs the following steps:

1. **Initialization** - Creates directories and sets up logging
2. **Pre-flight Checks** - Verifies SSH key, fixes permissions, checks OpenSSH client
3. **Trigger Remote Backup** - SSHs to server and runs `sudo ./backup.sh`
4. **Wait for Sync** - Waits 5 seconds for file system to sync
5. **Verify Backup** - Confirms backup file exists on server
6. **Download Backup** - Downloads the newly created backup file via SCP
7. **Verify Download** - Checks file integrity and size
8. **Local Cleanup** - Deletes local backups older than 7 days
9. **Summary** - Logs all operations and provides summary

#### Important Notes

- **Automatic Schedule**: Runs daily at 2:00 AM IST via Windows Task Scheduler
- **Dual Storage**: Backups are stored on both server and local machine
- **7-Day Retention**: Old backups (both server and local) are automatically deleted
- **Permission Fix**: Automatically fixes SSH key permissions before each backup
- **Compressed Format**: Backups are stored as `.sql.gz` files for space efficiency
- **Logs**: Detailed logs stored in `D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\logs\`

#### Manual Server Backup

To trigger a backup directly on the server (without downloading):

```bash
ssh -i "your-key.pem" ubuntu@your-server "cd /opt/digicard && sudo ./backup.sh"
```

Or from server terminal:

```bash
cd /opt/digicard
sudo ./backup.sh
```

---

## Security Checklist

Before going to production, ensure:

- [ ] SSL certificate is properly configured
- [ ] `APP_DOMAIN` is set to your production domain (e.g., https://app.card2contacts.com)
- [ ] `.env.production.local` created with production values
- [ ] POSTGRES_PASSWORD is set to strong random string
- [ ] SECRET_KEY is set to a strong random value
- [ ] GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET configured for your domain
- [ ] GROQ_API_KEY and MISTRAL_API_KEY configured
- [ ] SMTP credentials configured
- [ ] Firewall is configured (only 80, 443 open)
- [ ] Database is not accessible from outside (only 127.0.0.1:5432)
- [ ] ALLOWED_ORIGINS is restricted to your domain (automatically derived from APP_DOMAIN)
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
