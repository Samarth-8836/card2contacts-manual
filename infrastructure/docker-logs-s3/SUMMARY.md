# Docker Logs Export to S3 - Summary

## What Was Built

A complete solution for automatically exporting Docker container logs from your EC2 instance to AWS S3 every 5 minutes.

## Files Created

### Scripts (`infrastructure/docker-logs-s3/scripts/`)

1. **common-functions.sh**
   - Reusable functions for log operations
   - Timestamp management
   - Gzip compression
   - S3 upload handling
   - Error logging

2. **export-backend-logs.sh**
   - Exports logs from `scanner_backend` container
   - Incremenal export using timestamps
   - Compresses with gzip
   - Uploads to `s3://prod-app.card2contacts.com/prod/backend/`
   - Naming: `backend-logs-YYYY-MM-DD_HH-MM-SS.log.gz`

3. **export-db-logs.sh**
   - Exports logs from `scanner_db` container
   - Incremenal export using timestamps
   - Compresses with gzip
   - Uploads to `s3://prod-app.card2contacts.com/prod/db/`
   - Naming: `db-logs-YYYY-MM-DD_HH-MM-SS.log.gz`

### Systemd Services (`infrastructure/docker-logs-s3/systemd/`)

1. **backend-logs-export.service**
   - Runs backend log export script
   - Executed on timer trigger
   - Logs output to systemd journal

2. **backend-logs-export.timer**
   - Triggers every 5 minutes (`OnCalendar=*:0/5`)
   - Randomized delay of 10 seconds to avoid S3 API spikes
   - Persistent across reboots

3. **db-logs-export.service**
   - Runs database log export script
   - Executed on timer trigger
   - Logs output to systemd journal

4. **db-logs-export.timer**
   - Triggers every 5 minutes (`OnCalendar=*:0/5`)
   - Randomized delay of 10 seconds to avoid S3 API spikes
   - Persistent across reboots

### S3 Policies (`infrastructure/docker-logs-s3/s3-policies/`)

1. **iam-policy.json**
   - IAM policy for S3 upload permissions
   - Allows PutObject to specific paths
   - Attach to EC2 instance role

2. **lifecycle-policy.json**
   - S3 lifecycle policy
   - Moves logs to Standard-IA after 15 days
   - Applies to both `prod/backend/` and `prod/db/`

### Documentation

1. **README.md**
   - Comprehensive documentation
   - Architecture overview
   - Installation instructions
   - Configuration guide
   - Monitoring commands
   - Troubleshooting section

2. **QUICKSTART.md**
   - Quick installation guide
   - 5-minute setup
   - Common commands
   - Quick troubleshooting

3. **deploy.sh**
   - Automated deployment script
   - Checks prerequisites
   - Installs all components
   - Verifies installation

## Key Features

### ✅ Incremental Log Export
- Only captures new logs since last export
- No duplicate logs in S3
- Uses Docker `--since` flag with timestamp tracking

### ✅ Robust Scheduling
- Systemd timers (more reliable than cron)
- Persists across reboots
- Automatic restart on failure

### ✅ Compression
- Gzip compression reduces storage by ~70%
- Compressed files in S3
- Faster uploads and lower costs

### ✅ Error Handling
- Comprehensive logging
- Timestamp only updated on successful upload
- Handles empty log periods gracefully

### ✅ Cost Optimization
- S3 lifecycle policy moves to Standard-IA after 15 days
- Standard-IA is ~45% cheaper than Standard
- ~70% storage reduction from compression

### ✅ Monitoring
- Export logs in `/var/log/docker-logs-s3/export.log`
- Systemd journal for service logs
- Easy to verify S3 uploads

## S3 File Structure

```
prod-app.card2contacts.com/
├── prod/backend/
│   ├── backend-logs-2026-01-29_14-30-00.log.gz
│   ├── backend-logs-2026-01-29_14-35-00.log.gz
│   ├── backend-logs-2026-01-29_14-40-00.log.gz
│   └── ...
└── prod/db/
    ├── db-logs-2026-01-29_14-30-00.log.gz
    ├── db-logs-2026-01-29_14-35-00.log.gz
    ├── db-logs-2026-01-29_14-40-00.log.gz
    └── ...
```

## Deployment Steps

### Option 1: Automated Deployment (Recommended)

```bash
# 1. Copy files to EC2
scp -r infrastructure/docker-logs-s3/ user@ec2:/tmp/

# 2. SSH to EC2
ssh user@ec2

# 3. Run deployment script
cd /tmp/docker-logs-s3
sudo ./deploy.sh

# 4. Apply S3 lifecycle policy
aws s3api put-bucket-lifecycle-configuration \
  --bucket prod-app.card2contacts.com \
  --lifecycle-configuration file://s3-policies/lifecycle-policy.json
```

### Option 2: Manual Deployment

See README.md for detailed manual installation steps.

## Prerequisites

1. **EC2 Instance**
   - Docker running with `scanner_backend` and `scanner_db` containers
   - AWS CLI installed
   - systemd available (standard on Linux)

2. **AWS Resources**
   - S3 bucket: `prod-app.card2contacts.com`
   - IAM permissions (from `s3-policies/iam-policy.json`)

## Verification Commands

```bash
# Check timer status
sudo systemctl list-timers | grep logs-export

# View recent exports
sudo journalctl -u backend-logs-export.service -n 50

# Check S3 uploads
aws s3 ls s3://prod-app.card2contacts.com/prod/backend/ --recursive

# Manually test export
sudo /opt/docker-logs-s3/scripts/export-backend-logs.sh
```

## Cost Estimates

### Storage Costs (us-east-1)
- **Standard**: $0.023/GB/month
- **Standard-IA**: $0.0125/GB/month (45% savings)

### Example Calculation
Assume 100 MB of logs per day:
- **Without compression**: 3 GB/month ≈ $0.07/month
- **With gzip (70% reduction)**: 0.9 GB/month ≈ $0.02/month
- **After 15 days (mixed storage)**: ≈ $0.015/month

**Total savings**: ~78% compared to uncompressed Standard storage

## Next Steps

1. ✅ Deploy to EC2 instance
2. ✅ Apply S3 lifecycle policy
3. ✅ Verify first export
4. 📊 Set up S3 metrics in CloudWatch
5. 📊 Consider CloudWatch Alarms for failed exports
6. 📊 Consider integration with log analysis tools (Splunk, ELK, etc.)

## Support

For detailed documentation:
- `README.md` - Complete documentation
- `QUICKSTART.md` - Quick start guide

For issues:
- Check `/var/log/docker-logs-s3/export.log`
- Check systemd journal: `journalctl -u backend-logs-export.service`
- Review troubleshooting sections in documentation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  EC2 Instance                                                 │
│                                                              │
│  scanner_backend ──┐                                         │
│  scanner_db ───────┼──▶ Export Scripts ──▶ S3 Upload        │
│                    │      (every 5 min)     (gzip)          │
│  systemd timers ───┘                                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  S3: prod-app.card2contacts.com                              │
│                                                              │
│  prod/backend/backend-logs-*.log.gz                         │
│  prod/db/db-logs-*.log.gz                                    │
│                                                              │
│  Lifecycle: Move to Standard-IA after 15 days               │
└─────────────────────────────────────────────────────────────┘
```

## Branch

All files created on branch: `performance/stability-fix`

Ready for deployment to production EC2 instance!
