# Docker Logs Export to S3

This solution exports Docker container logs from your EC2 instance to AWS S3 every 5 minutes using systemd timers. Logs are compressed with gzip and organized by service.

## Features

- **Incremental Log Export**: Only captures new logs since last export (no duplicates)
- **Systemd Timers**: Robust scheduling that persists across reboots
- **Gzip Compression**: Reduces S3 storage costs by ~70%
- **Timestamp Tracking**: Maintains state to ensure no duplicate logs
- **S3 Lifecycle**: Automatically moves to Standard-IA after 15 days
- **Error Handling**: Comprehensive logging and failure recovery

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  EC2 Instance                                                 │
│                                                              │
│  ┌──────────────┐      ┌────────────────────────────────┐   │
│  │ scanner_     │      │ /opt/docker-logs-s3/           │   │
│  │ backend      ├─────▶│  ├── scripts/                   │   │
│  │ (container)  │      │  │   ├── common-functions.sh   │   │
│  └──────────────┘      │  │   ├── export-backend-logs.sh│   │
│                        │  │   └── export-db-logs.sh     │   │
│  ┌──────────────┐      │  ├── systemd/                   │   │
│  │ scanner_db   │      │  │   ├── backend-logs-export.*  │   │
│  │ (container)  ├─────▶│  │   └── db-logs-export.*      │   │
│  └──────────────┘      │  └── /var/log/docker-logs-s3/  │   │
│                        │      ├── export.log             │   │
│                        │      └── timestamps/             │   │
│  ┌──────────────────┐  │          ├── backend.last       │   │
│  │ systemd timers   │  │          └── db.last            │   │
│  │ (every 5 min)   │  │                                  │   │
│  └──────────────────┘  └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ aws s3 cp (gzip compressed)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  AWS S3                                                      │
│                                                              │
│  prod-app.card2contacts.com/                                │
│  ├── prod/backend/                                          │
│  │   ├── backend-logs-2026-01-29_14-30-00.log.gz            │
│  │   ├── backend-logs-2026-01-29_14-35-00.log.gz            │
│  │   └── ...                                                │
│  └── prod/db/                                               │
│      ├── db-logs-2026-01-29_14-30-00.log.gz                 │
│      ├── db-logs-2026-01-29_14-35-00.log.gz                 │
│      └── ...                                                │
│                                                              │
│  Lifecycle: Move to Standard-IA after 15 days               │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. AWS IAM Permissions

The EC2 instance must have permissions to upload to S3. Either:

**Option A: IAM Role (Recommended)**
- Attach the IAM policy from `s3-policies/iam-policy.json` to your EC2 instance role

**Option B: AWS CLI Credentials**
- Configure AWS CLI with appropriate credentials
- `aws configure`

### 2. Required Software on EC2

```bash
# Check if installed
aws --version          # AWS CLI
systemctl --version    # systemd (most Linux distributions)
docker --version       # Docker
gzip --version         # gzip compression
```

### 3. Verify Container Names

```bash
docker ps --format "{{.Names}}"
# Expected output:
# scanner_backend
# scanner_db
# scanner_frontend
```

## Installation

### Step 1: Create Directory Structure

```bash
sudo mkdir -p /opt/docker-logs-s3/scripts
sudo mkdir -p /opt/docker-logs-s3/systemd
```

### Step 2: Copy Scripts

From your local machine (or on the EC2 instance if files are there):

```bash
# Copy script files
sudo cp infrastructure/docker-logs-s3/scripts/*.sh /opt/docker-logs-s3/scripts/

# Make scripts executable
sudo chmod +x /opt/docker-logs-s3/scripts/*.sh
```

### Step 3: Copy systemd Files

```bash
# Copy systemd service and timer files
sudo cp infrastructure/docker-logs-s3/systemd/*.service /etc/systemd/system/
sudo cp infrastructure/docker-logs-s3/systemd/*.timer /etc/systemd/system/
```

### Step 4: Reload systemd

```bash
sudo systemctl daemon-reload
```

### Step 5: Enable and Start Timers

```bash
# Enable and start backend logs timer
sudo systemctl enable --now backend-logs-export.timer

# Enable and start database logs timer
sudo systemctl enable --now db-logs-export.timer
```

### Step 6: Verify Installation

```bash
# Check timer status
sudo systemctl list-timers | grep logs-export

# Check if timers are active
sudo systemctl status backend-logs-export.timer
sudo systemctl status db-logs-export.timer

# View next scheduled run
systemctl show backend-logs-export.timer -p NextElapseUSecRealtime
systemctl show db-logs-export.timer -p NextElapseUSecRealtime
```

## Configuration

### Adjust Export Interval

Edit the timer files to change the interval:

```bash
# Backend timer
sudo nano /etc/systemd/system/backend-logs-export.timer

# Database timer
sudo nano /etc/systemd/system/db-logs-export.timer
```

Change `OnCalendar=*:0/5` to desired interval:
- Every 10 minutes: `OnCalendar=*:0/10`
- Every 15 minutes: `OnCalendar=*:0/15`
- Every hour: `OnCalendar=hourly`

After changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart backend-logs-export.timer
sudo systemctl restart db-logs-export.timer
```

### Change S3 Bucket

Edit `/opt/docker-logs-s3/scripts/common-functions.sh`:

```bash
S3_BUCKET="your-bucket-name"
```

## Monitoring

### Check Timer Execution

```bash
# View last 50 lines of service execution log
sudo journalctl -u backend-logs-export.service -n 50
sudo journalctl -u db-logs-export.service -n 50

# Follow logs in real-time
sudo journalctl -u backend-logs-export.service -f
sudo journalctl -u db-logs-export.service -f
```

### Check Export Log

```bash
# View export log
sudo cat /var/log/docker-logs-s3/export.log

# Follow export log
sudo tail -f /var/log/docker-logs-s3/export.log
```

### Check S3 Uploads

```bash
# List backend logs
aws s3 ls s3://prod-app.card2contacts.com/prod/backend/ --recursive

# List database logs
aws s3 ls s3://prod-app.card2contacts.com/prod/db/ --recursive

# Count uploaded files
aws s3 ls s3://prod-app.card2contacts.com/prod/backend/ --recursive | wc -l
aws s3 ls s3://prod-app.card2contacts.com/prod/db/ --recursive | wc -l
```

### Verify Timestamps

```bash
# Check last export timestamps
sudo cat /var/log/docker-logs-s3/timestamps/backend.last
sudo cat /var/log/docker-logs-s3/timestamps/db.last
```

## Manual Testing

### Test Backend Export Manually

```bash
# Run backend export script manually
sudo /opt/docker-logs-s3/scripts/export-backend-logs.sh

# Check exit code
echo $?
```

### Test Database Export Manually

```bash
# Run database export script manually
sudo /opt/docker-logs-s3/scripts/export-db-logs.sh

# Check exit code
echo $?
```

### Test Service Trigger

```bash
# Trigger service immediately
sudo systemctl start backend-logs-export.service
sudo systemctl start db-logs-export.service

# Check service status
sudo systemctl status backend-logs-export.service
sudo systemctl status db-logs-export.service
```

## Troubleshooting

### Issue: Service Fails to Start

**Check service status:**
```bash
sudo systemctl status backend-logs-export.service
sudo journalctl -u backend-logs-export.service -n 100
```

**Common causes:**
1. AWS CLI not configured
2. IAM permissions missing
3. Container name incorrect
4. Docker not running

### Issue: Logs Not Being Captured

**Verify container is running:**
```bash
docker ps | grep -E "scanner_backend|scanner_db"
```

**Check if container is producing logs:**
```bash
docker logs --tail 20 scanner_backend
docker logs --tail 20 scanner_db
```

### Issue: Upload to S3 Fails

**Test AWS CLI connection:**
```bash
aws s3 ls s3://prod-app.card2contacts.com/
```

**Check IAM permissions:**
```bash
aws sts get-caller-identity
```

### Issue: Duplicate Logs in S3

**Check timestamp files:**
```bash
ls -la /var/log/docker-logs-s3/timestamps/
cat /var/log/docker-logs-s3/timestamps/backend.last
```

If timestamps are incorrect, you can reset them:
```bash
sudo rm /var/log/docker-logs-s3/timestamps/*.last
```

Next export will use `--since 5m` (last 5 minutes of logs).

### Issue: Timer Not Triggering

**Check if timer is enabled:**
```bash
systemctl is-enabled backend-logs-export.timer
systemctl is-enabled db-logs-export.timer
```

**Check timer status:**
```bash
systemctl status backend-logs-export.timer
systemctl list-timers
```

## S3 Lifecycle Policy

Apply the lifecycle policy from `s3-policies/lifecycle-policy.json`:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket prod-app.card2contacts.com \
  --lifecycle-configuration file://s3-policies/lifecycle-policy.json
```

**Policy Details:**
- Moves logs to Standard-IA after 15 days
- Applies to both `prod/backend/` and `prod/db/` prefixes
- Aborts incomplete multipart uploads after 7 days

**Verify lifecycle policy:**
```bash
aws s3api get-bucket-lifecycle-configuration \
  --bucket prod-app.card2contacts.com
```

## File Naming Convention

Logs are named with timestamps: `service-logs-YYYY-MM-DD_HH-MM-SS.log.gz`

Examples:
- `backend-logs-2026-01-29_14-30-00.log.gz`
- `backend-logs-2026-01-29_14-35-00.log.gz`
- `db-logs-2026-01-29_14-30-00.log.gz`

This makes it easy to:
- Sort chronologically
- Identify export time
- Query by time range in S3

## Maintenance

### Rotate Export Log

The export log (`/var/log/docker-logs-s3/export.log`) can grow over time. Add log rotation:

```bash
sudo nano /etc/logrotate.d/docker-logs-s3
```

Content:
```
/var/log/docker-logs-s3/export.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
```

### Disable Service

To temporarily stop log exports:

```bash
sudo systemctl stop backend-logs-export.timer
sudo systemctl stop db-logs-export.timer

# To restart later
sudo systemctl start backend-logs-export.timer
sudo systemctl start db-logs-export.timer
```

To permanently disable:

```bash
sudo systemctl disable backend-logs-export.timer
sudo systemctl disable db-logs-export.timer
```

## Uninstallation

To completely remove the log export system:

```bash
# Stop and disable timers
sudo systemctl stop backend-logs-export.timer db-logs-export.timer
sudo systemctl disable backend-logs-export.timer db-logs-export.timer

# Remove systemd files
sudo rm /etc/systemd/system/backend-logs-export.service
sudo rm /etc/systemd/system/backend-logs-export.timer
sudo rm /etc/systemd/system/db-logs-export.service
sudo rm /etc/systemd/system/db-logs-export.timer

# Reload systemd
sudo systemctl daemon-reload

# Remove scripts
sudo rm -rf /opt/docker-logs-s3

# Remove log directory (optional)
sudo rm -rf /var/log/docker-logs-s3
```

## Log Retention Strategy

Recommendations for log retention:

| Age | Storage Class | Cost Benefit |
|-----|--------------|--------------|
| 0-14 days | Standard | Fast access for troubleshooting |
| 15-89 days | Standard-IA | Lower cost for infrequent access |
| 90+ days | Glacier Deep Archive | Lowest cost for archival |

**Cost Savings Example:**
- Standard: $0.023/GB/month
- Standard-IA: $0.0125/GB/month (45% savings)
- Glacier Deep Archive: $0.00099/GB/month (96% savings)

## Support

For issues or questions:
1. Check the export log: `/var/log/docker-logs-s3/export.log`
2. Check systemd journal: `journalctl -u backend-logs-export.service`
3. Verify AWS connectivity and IAM permissions
4. Review this README's troubleshooting section

## Quick Reference

```bash
# Check timer status
sudo systemctl list-timers | grep logs-export

# View recent exports
sudo journalctl -u backend-logs-export.service -n 20

# Check S3 uploads
aws s3 ls s3://prod-app.card2contacts.com/prod/backend/ --recursive

# Test manually
sudo /opt/docker-logs-s3/scripts/export-backend-logs.sh

# Restart timer
sudo systemctl restart backend-logs-export.timer

# Disable temporarily
sudo systemctl stop backend-logs-export.timer
```
