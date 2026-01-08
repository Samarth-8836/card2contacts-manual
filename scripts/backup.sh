#!/bin/bash
# ==========================================
# DIGICARD ENTERPRISE - DATABASE BACKUP
# ==========================================
# This script creates a backup of the PostgreSQL database

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}DigiCard Enterprise${NC}"
echo -e "${GREEN}Database Backup${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Create backup directory
BACKUP_DIR="backups"
mkdir -p $BACKUP_DIR

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/digicard_backup_$TIMESTAMP.sql"

# Load environment variables
if [ -f ".env.production" ]; then
    source .env.production
else
    echo -e "${RED}Error: .env.production not found${NC}"
    exit 1
fi

# Create backup
echo -e "${YELLOW}Creating database backup...${NC}"
docker exec digicard-database pg_dump -U ${DB_USER:-digicard_admin} ${DB_NAME:-digicard_enterprise} > $BACKUP_FILE

# Compress backup
echo -e "${YELLOW}Compressing backup...${NC}"
gzip $BACKUP_FILE

echo ""
echo -e "${GREEN}✓ Backup created successfully!${NC}"
echo ""
echo -e "${YELLOW}Backup file:${NC} ${BACKUP_FILE}.gz"
echo ""

# Clean up old backups (keep last 7 days)
echo -e "${YELLOW}Cleaning up old backups...${NC}"
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo -e "${GREEN}Done!${NC}"
