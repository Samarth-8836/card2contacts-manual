#!/bin/bash
# ==========================================
# DIGICARD ENTERPRISE - SSL CERTIFICATE GENERATOR
# ==========================================
# This script generates self-signed SSL certificates for testing
# For production, use Let's Encrypt (see deployment guide)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}DigiCard Enterprise${NC}"
echo -e "${GREEN}SSL Certificate Generator${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Create SSL directory if it doesn't exist
mkdir -p ssl

# Ask for domain name
read -p "Enter your domain name (e.g., yourdomain.com): " DOMAIN

if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Error: Domain name is required${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Generating self-signed SSL certificate for ${DOMAIN}...${NC}"
echo ""

# Generate private key
openssl genrsa -out ssl/key.pem 2048

# Generate certificate signing request
openssl req -new -key ssl/key.pem -out ssl/cert.csr \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=${DOMAIN}"

# Generate self-signed certificate (valid for 365 days)
openssl x509 -req -days 365 -in ssl/cert.csr -signkey ssl/key.pem -out ssl/cert.pem

# Clean up CSR
rm ssl/cert.csr

echo ""
echo -e "${GREEN}✓ SSL certificate generated successfully!${NC}"
echo ""
echo -e "${YELLOW}Certificate files created:${NC}"
echo "  - ssl/cert.pem (Certificate)"
echo "  - ssl/key.pem (Private Key)"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
echo "  This is a SELF-SIGNED certificate suitable for testing only."
echo "  For production, use Let's Encrypt certificates (see deployment guide)."
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Update .env.production with your configuration"
echo "  2. Run: docker-compose up -d"
echo ""
