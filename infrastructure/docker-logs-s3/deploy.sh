#!/bin/bash

# Deployment script for Docker Logs Export to S3
# Run this script on your EC2 instance to set up automated log export

set -e

echo "======================================"
echo "Docker Logs Export to S3 - Deployment"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}"
   exit 1
fi

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Install with: sudo apt-get install awscli (Ubuntu/Debian)"
    echo "             sudo yum install awscli (CentOS/RHEL)"
    exit 1
fi
echo -e "${GREEN}✓ AWS CLI found${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}Error: systemd is not available${NC}"
    exit 1
fi
echo -e "${GREEN}✓ systemd found${NC}"

echo ""

# Check AWS CLI configuration
echo -e "${YELLOW}Checking AWS CLI configuration...${NC}"
if aws sts get-caller-identity &> /dev/null; then
    echo -e "${GREEN}✓ AWS CLI is configured${NC}"
    AWS_IDENTITY=$(aws sts get-caller-identity --query Account --output text)
    echo "  Account ID: ${AWS_IDENTITY}"
else
    echo -e "${YELLOW}⚠ AWS CLI not configured or permissions missing${NC}"
    echo "  Run: aws configure"
    echo "  Or ensure EC2 instance has appropriate IAM role"
fi

echo ""

# Verify container names
echo -e "${YELLOW}Verifying Docker containers...${NC}"
if docker ps --format "{{.Names}}" | grep -q "^scanner_backend$"; then
    echo -e "${GREEN}✓ scanner_backend container found${NC}"
else
    echo -e "${RED}Error: scanner_backend container not found${NC}"
    echo "  Available containers:"
    docker ps --format "{{.Names}}"
    exit 1
fi

if docker ps --format "{{.Names}}" | grep -q "^scanner_db$"; then
    echo -e "${GREEN}✓ scanner_db container found${NC}"
else
    echo -e "${RED}Error: scanner_db container not found${NC}"
    echo "  Available containers:"
    docker ps --format "{{.Names}}"
    exit 1
fi

echo ""

# Create directory structure
echo -e "${YELLOW}Creating directory structure...${NC}"
mkdir -p /opt/docker-logs-s3/scripts
mkdir -p /opt/docker-logs-s3/systemd
mkdir -p /var/log/docker-logs-s3/timestamps
echo -e "${GREEN}✓ Directories created${NC}"

echo ""

# Check if script files exist
echo -e "${YELLOW}Checking for script files...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_SCRIPT_DIR="${SCRIPT_DIR}/infrastructure/docker-logs-s3/scripts"

if [[ ! -d "${REPO_SCRIPT_DIR}" ]]; then
    echo -e "${RED}Error: Script directory not found at ${REPO_SCRIPT_DIR}${NC}"
    echo "Please run this script from the repository root directory"
    exit 1
fi

if [[ ! -f "${REPO_SCRIPT_DIR}/common-functions.sh" ]]; then
    echo -e "${RED}Error: common-functions.sh not found${NC}"
    exit 1
fi

if [[ ! -f "${REPO_SCRIPT_DIR}/export-backend-logs.sh" ]]; then
    echo -e "${RED}Error: export-backend-logs.sh not found${NC}"
    exit 1
fi

if [[ ! -f "${REPO_SCRIPT_DIR}/export-db-logs.sh" ]]; then
    echo -e "${RED}Error: export-db-logs.sh not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All script files found${NC}"

echo ""

# Copy scripts
echo -e "${YELLOW}Copying scripts...${NC}"
cp "${REPO_SCRIPT_DIR}/common-functions.sh" /opt/docker-logs-s3/scripts/
cp "${REPO_SCRIPT_DIR}/export-backend-logs.sh" /opt/docker-logs-s3/scripts/
cp "${REPO_SCRIPT_DIR}/export-db-logs.sh" /opt/docker-logs-s3/scripts/
chmod +x /opt/docker-logs-s3/scripts/*.sh
echo -e "${GREEN}✓ Scripts copied and made executable${NC}"

echo ""

# Copy systemd files
echo -e "${YELLOW}Copying systemd files...${NC}"
REPO_SYSTEMD_DIR="${SCRIPT_DIR}/infrastructure/docker-logs-s3/systemd"

cp "${REPO_SYSTEMD_DIR}/backend-logs-export.service" /etc/systemd/system/
cp "${REPO_SYSTEMD_DIR}/backend-logs-export.timer" /etc/systemd/system/
cp "${REPO_SYSTEMD_DIR}/db-logs-export.service" /etc/systemd/system/
cp "${REPO_SYSTEMD_DIR}/db-logs-export.timer" /etc/systemd/system/
echo -e "${GREEN}✓ Systemd files copied${NC}"

echo ""

# Reload systemd
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd daemon reloaded${NC}"

echo ""

# Enable and start timers
echo -e "${YELLOW}Enabling and starting timers...${NC}"
systemctl enable --now backend-logs-export.timer
systemctl enable --now db-logs-export.timer
echo -e "${GREEN}✓ Timers enabled and started${NC}"

echo ""

# Verify installation
echo -e "${YELLOW}Verifying installation...${NC}"

# Check timer status
if systemctl is-active --quiet backend-logs-export.timer; then
    echo -e "${GREEN}✓ Backend logs timer is active${NC}"
else
    echo -e "${RED}✗ Backend logs timer is not active${NC}"
    exit 1
fi

if systemctl is-active --quiet db-logs-export.timer; then
    echo -e "${GREEN}✓ Database logs timer is active${NC}"
else
    echo -e "${RED}✗ Database logs timer is not active${NC}"
    exit 1
fi

# Show next scheduled run
echo ""
echo -e "${YELLOW}Next scheduled runs:${NC}"
NEXT_BACKEND=$(systemctl show backend-logs-export.timer -p NextElapseUSecRealtime | cut -d= -f2)
NEXT_DB=$(systemctl show db-logs-export.timer -p NextElapseUSecRealtime | cut -d= -f2)
echo "  Backend: ${NEXT_BACKEND}"
echo "  Database: ${NEXT_DB}"

echo ""
echo "======================================"
echo -e "${GREEN}Installation completed successfully!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Apply S3 lifecycle policy:"
echo "   aws s3api put-bucket-lifecycle-configuration \\"
echo "     --bucket prod-app.card2contacts.com \\"
echo "     --lifecycle-configuration file://infrastructure/docker-logs-s3/s3-policies/lifecycle-policy.json"
echo ""
echo "2. Monitor first export:"
echo "   sudo journalctl -u backend-logs-export.service -f"
echo "   sudo journalctl -u db-logs-export.service -f"
echo ""
echo "3. Check S3 uploads:"
echo "   aws s3 ls s3://prod-app.card2contacts.com/prod/backend/ --recursive"
echo "   aws s3 ls s3://prod-app.card2contacts.com/prod/db/ --recursive"
echo ""
echo "For more information, see infrastructure/docker-logs-s3/README.md"
echo ""
