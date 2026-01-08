#!/bin/bash
# ==========================================
# DIGICARD ENTERPRISE - DEPLOYMENT SCRIPT
# ==========================================
# This script deploys the application to production

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}DigiCard Enterprise${NC}"
echo -e "${BLUE}Production Deployment${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo -e "${RED}Error: .env.production file not found${NC}"
    echo "Please create .env.production from .env.example and fill in your configuration"
    exit 1
fi

# Check if SSL certificates exist
if [ ! -f "ssl/cert.pem" ] || [ ! -f "ssl/key.pem" ]; then
    echo -e "${YELLOW}Warning: SSL certificates not found${NC}"
    echo ""
    echo "Choose an option:"
    echo "  1. Generate self-signed certificate (testing only)"
    echo "  2. Use Let's Encrypt (recommended for production)"
    echo "  3. Exit (I'll add certificates manually)"
    echo ""
    read -p "Enter your choice (1-3): " SSL_CHOICE

    case $SSL_CHOICE in
        1)
            bash scripts/generate-ssl-cert.sh
            ;;
        2)
            bash scripts/setup-letsencrypt.sh
            ;;
        3)
            echo -e "${YELLOW}Please add your SSL certificates to the ssl/ directory:${NC}"
            echo "  - ssl/cert.pem (Certificate)"
            echo "  - ssl/key.pem (Private Key)"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
fi

echo ""
echo -e "${GREEN}Starting deployment...${NC}"
echo ""

# Pull latest images
echo -e "${YELLOW}[1/5] Pulling latest base images...${NC}"
docker-compose pull database certbot

# Build application images
echo ""
echo -e "${YELLOW}[2/5] Building application images...${NC}"
docker-compose build --no-cache

# Stop existing containers
echo ""
echo -e "${YELLOW}[3/5] Stopping existing containers...${NC}"
docker-compose down

# Start services
echo ""
echo -e "${YELLOW}[4/5] Starting services...${NC}"
docker-compose up -d

# Wait for services to be ready
echo ""
echo -e "${YELLOW}[5/5] Waiting for services to be ready...${NC}"
sleep 20

# Check service health
echo ""
echo -e "${YELLOW}Checking service health...${NC}"
echo ""

if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓ Services are running${NC}"
    echo ""
    docker-compose ps
    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo -e "${YELLOW}Your application is now running:${NC}"
    echo "  - Frontend: https://your-domain.com"
    echo "  - Backend API: https://your-domain.com/api"
    echo "  - Database: localhost:5432"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo "  - View logs: docker-compose logs -f"
    echo "  - Stop services: docker-compose down"
    echo "  - Restart services: docker-compose restart"
    echo "  - View status: docker-compose ps"
    echo ""
else
    echo -e "${RED}✗ Some services failed to start${NC}"
    echo ""
    echo "Check logs with: docker-compose logs"
    exit 1
fi
