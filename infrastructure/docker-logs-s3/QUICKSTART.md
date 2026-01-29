# Docker Logs Export to S3 - Quick Start

This guide helps you quickly set up automated log export from your Docker containers to AWS S3.

## Prerequisites Checklist

- [ ] EC2 instance with Docker running `scanner_backend` and `scanner_db` containers
- [ ] AWS S3 bucket: `prod-app.card2contacts.com` created
- [ ] AWS CLI installed on EC2 instance
- [ ] EC2 instance has IAM role with S3 write permissions (or AWS CLI configured)

## Quick Installation (5 minutes)

### Step 1: Transfer Files to EC2

From your local machine:

```bash
# Copy the entire docker-logs-s3 directory to EC2
scp -r infrastructure/docker-logs-s3/ user@your-ec2-instance:/tmp/
```

### Step 2: SSH into EC2

```bash
ssh user@your-ec2-instance
```

### Step 3: Run Deployment Script

```bash
cd /tmp/docker-logs-s3
sudo ./deploy.sh
```

The script will:
- Check prerequisites (AWS CLI, Docker, systemd)
- Verify container names
- Install scripts and systemd services
- Enable and start timers
- Verify installation

### Step 4: Apply S3 Lifecycle Policy

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket prod-app.card2contacts.com \
  --lifecycle-configuration file://s3-policies/lifecycle-policy.json
```

This moves logs to Standard-IA after 15 days to reduce costs.

### Step 5: Verify First Export

Wait up to 5 minutes for the first export, or trigger manually:

```bash
# Trigger immediate export
sudo systemctl start backend-logs-export.service
sudo systemctl start db-logs-export.service

# Check status
sudo systemctl status backend-logs-export.service
sudo systemctl status db-logs-export.service
```

### Step 6: Verify S3 Uploads

```bash
# List backend logs
aws s3 ls s3://prod-app.card2contacts.com/prod/backend/ --recursive

# List database logs
aws s3 ls s3://prod-app.card2contacts.com/prod/db/ --recursive
```

## Common Commands

```bash
# Check timer status
sudo systemctl list-timers | grep logs-export

# View recent export logs
sudo journalctl -u backend-logs-export.service -n 50
sudo journalctl -u db-logs-export.service -n 50

# Monitor exports in real-time
sudo journalctl -u backend-logs-export.service -f

# Check export log
sudo cat /var/log/docker-logs-s3/export.log

# Manually test export
sudo /opt/docker-logs-s3/scripts/export-backend-logs.sh
sudo /opt/docker-logs-s3/scripts/export-db-logs.sh

# Stop timers temporarily
sudo systemctl stop backend-logs-export.timer
sudo systemctl stop db-logs-export.timer

# Restart timers
sudo systemctl start backend-logs-export.timer
sudo systemctl start db-logs-export.timer
```

## Troubleshooting

### Export Not Working?

1. **Check service status:**
   ```bash
   sudo systemctl status backend-logs-export.service
   ```

2. **View service logs:**
   ```bash
   sudo journalctl -u backend-logs-export.service -n 100
   ```

3. **Check AWS CLI:**
   ```bash
   aws s3 ls s3://prod-app.card2contacts.com/
   ```

4. **Verify container names:**
   ```bash
   docker ps --format "{{.Names}}"
   ```

### Duplicate Logs?

Check timestamp files:
```bash
ls -la /var/log/docker-logs-s3/timestamps/
cat /var/log/docker-logs-s3/timestamps/backend.last
```

If incorrect, delete them:
```bash
sudo rm /var/log/docker-logs-s3/timestamps/*.last
```

### AWS Permissions Error?

Make sure EC2 instance has IAM role with policy from `s3-policies/iam-policy.json`, or configure AWS CLI:
```bash
aws configure
```

## File Locations

- **Scripts**: `/opt/docker-logs-s3/scripts/`
- **Systemd files**: `/etc/systemd/system/backend-logs-export.*`, `/etc/systemd/system/db-logs-export.*`
- **Export log**: `/var/log/docker-logs-s3/export.log`
- **Timestamps**: `/var/log/docker-logs-s3/timestamps/`

## How It Works

1. **Every 5 minutes**, systemd timers trigger export services
2. **Scripts** read the last export timestamp from files
3. **Docker logs** command retrieves logs since last timestamp
4. **Logs** are compressed with gzip (~70% reduction)
5. **Compressed logs** are uploaded to S3 with timestamp filename
6. **Timestamp file** is updated with current time
7. **Next export** will only get new logs (incremental)

## S3 Lifecycle Policy

The included lifecycle policy:
- **Days 0-14**: Standard storage (fast access)
- **Day 15+**: Standard-IA (lower cost, ~45% savings)

To apply or update:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket prod-app.card2contacts.com \
  --lifecycle-configuration file://s3-policies/lifecycle-policy.json
```

## Support

For detailed documentation, see `README.md` in the docker-logs-s3 directory.

## Next Steps

1. ✅ Log exports are running every 5 minutes
2. ✅ Logs are compressed and uploaded to S3
3. ✅ Logs move to Standard-IA after 15 days
4. 📊 Consider setting up S3 metrics and alarms
5. 📊 Consider integrating with CloudWatch Logs or SIEM
