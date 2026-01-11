#!/bin/bash

# DigiCard Enterprise - Database Backup Script
# This script backs up the PostgreSQL database and keeps only the last 7 days

set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/digicard/backups"
DOCKER_COMPOSE_FILE="/opt/digicard/docker-compose.production.yml"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

echo "[$(date)] Starting database backup..."

# Backup database
docker-compose -f $DOCKER_COMPOSE_FILE exec -T db pg_dump -U admin scanner_prod > $BACKUP_DIR/db_backup_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/db_backup_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +7 -delete

echo "[$(date)] Backup completed: db_backup_$DATE.sql.gz"

# Show disk usage
echo "Backup directory size:"
du -sh $BACKUP_DIR

# List recent backups
echo "Recent backups:"
ls -lh $BACKUP_DIR | tail -10
