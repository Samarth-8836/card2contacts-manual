#!/bin/bash
# ==========================================
# DIGICARD ENTERPRISE - LET'S ENCRYPT SETUP
# ==========================================
# This script sets up Let's Encrypt SSL certificates for production

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}DigiCard Enterprise${NC}"
echo -e "${GREEN}Let's Encrypt SSL Setup${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Ask for domain and email
read -p "Enter your domain name (e.g., yourdomain.com): " DOMAIN
read -p "Enter your email address: " EMAIL

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo -e "${RED}Error: Domain name and email are required${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Setting up Let's Encrypt for ${DOMAIN}...${NC}"
echo ""

# Create necessary directories
mkdir -p ssl
mkdir -p nginx

# Check if nginx configuration exists
if [ ! -f "nginx/default.conf" ]; then
    echo -e "${RED}Error: nginx/default.conf not found${NC}"
    echo "Please ensure you have the nginx configuration files in place."
    exit 1
fi

# Start only the frontend and database for initial setup
echo -e "${YELLOW}Starting frontend service...${NC}"
docker-compose up -d frontend database

# Wait for nginx to be ready
echo -e "${YELLOW}Waiting for nginx to be ready...${NC}"
sleep 10

# Request certificate
echo -e "${YELLOW}Requesting SSL certificate from Let's Encrypt...${NC}"
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN \
    -d www.$DOMAIN

# Copy certificates to ssl directory
echo -e "${YELLOW}Copying certificates...${NC}"
docker cp digicard-certbot:/etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/cert.pem
docker cp digicard-certbot:/etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/key.pem

# Restart services
echo -e "${YELLOW}Restarting services...${NC}"
docker-compose restart frontend

echo ""
echo -e "${GREEN}✓ Let's Encrypt SSL certificate installed successfully!${NC}"
echo ""
echo -e "${YELLOW}Certificate files created:${NC}"
echo "  - ssl/cert.pem (Certificate)"
echo "  - ssl/key.pem (Private Key)"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Your site is now secured with HTTPS"
echo "  2. Certificates will auto-renew every 12 hours"
echo "  3. Start all services: docker-compose up -d"
echo ""
