#!/bin/bash
# ==========================================
# DIGICARD ENTERPRISE - DATABASE RESTORE
# ==========================================
# This script restores the PostgreSQL database from a backup

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}DigiCard Enterprise${NC}"
echo -e "${GREEN}Database Restore${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Check if backup file is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Backup file not specified${NC}"
    echo ""
    echo "Usage: ./scripts/restore.sh <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lh backups/*.sql.gz 2>/dev/null || echo "  No backups found"
    exit 1
fi

BACKUP_FILE=$1

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

# Load environment variables
if [ -f ".env.production" ]; then
    source .env.production
else
    echo -e "${RED}Error: .env.production not found${NC}"
    exit 1
fi

# Confirm restore
echo -e "${YELLOW}⚠️  WARNING: This will replace the current database!${NC}"
echo ""
read -p "Are you sure you want to restore from $BACKUP_FILE? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}Decompressing backup...${NC}"
gunzip -c $BACKUP_FILE > /tmp/restore.sql

echo -e "${YELLOW}Stopping backend service...${NC}"
docker-compose stop backend

echo -e "${YELLOW}Restoring database...${NC}"
docker exec -i digicard-database psql -U ${DB_USER:-digicard_admin} ${DB_NAME:-digicard_enterprise} < /tmp/restore.sql

echo -e "${YELLOW}Starting backend service...${NC}"
docker-compose start backend

# Clean up
rm /tmp/restore.sql

echo ""
echo -e "${GREEN}✓ Database restored successfully!${NC}"
echo ""
