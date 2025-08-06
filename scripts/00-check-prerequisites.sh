#!/bin/bash
# scripts/00-check-prerequisites.sh
# Kiểm tra các điều kiện cần thiết trước khi deploy

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Checking prerequisites for HG Chatbot K8s deployment...${NC}"
echo ""

ERRORS=0
WARNINGS=0

# Function to check command exists
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✅ $1 is installed${NC}"
    else
        echo -e "${RED}❌ $1 is NOT installed${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅ $1 exists${NC}"
    else
        echo -e "${RED}❌ $1 NOT found${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check directory
check_dir() {
    if [ -d "$1" ]; then
        if [ -z "$(ls -A $1 2>/dev/null)" ]; then
            echo -e "${YELLOW}⚠️  $1 exists but is EMPTY${NC}"
            WARNINGS=$((WARNINGS + 1))
        else
            echo -e "${GREEN}✅ $1 exists and has content${NC}"
        fi
    else
        echo -e "${RED}❌ $1 NOT found${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

# 1. Check required commands
echo -e "${BLUE}1. Checking required commands...${NC}"
check_command kubectl
check_command docker
check_command ssh
check_command rsync
echo ""

# 2. Check project structure
echo -e "${BLUE}2. Checking project structure...${NC}"
check_dir "app"
check_dir "k8s"
check_dir "scripts"
check_dir "model_weights"
check_file "requirements.txt"
check_file "Dockerfile"
echo ""

# 3. Check K8s cluster connection
echo -e "${BLUE}3. Checking Kubernetes cluster...${NC}"
if kubectl cluster-info &>/dev/null; then
    echo -e "${GREEN}✅ Connected to K8s cluster${NC}"
    
    # Check nodes
    NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
    echo -e "   Found $NODE_COUNT nodes"
    kubectl get nodes --no-headers | while read line; do
        echo -e "   - $line"
    done
    
    # Check for GPU nodes
    GPU_NODES=$(kubectl get nodes -l nvidia.com/gpu=true --no-headers 2>/dev/null | wc -l)
    if [ $GPU_NODES -gt 0 ]; then
        echo -e "${GREEN}✅ Found $GPU_NODES GPU-enabled nodes${NC}"
    else
        echo -e "${YELLOW}⚠️  No GPU-enabled nodes found${NC}"
        echo "   Label GPU nodes with: kubectl label nodes <node-name> nvidia.com/gpu=true"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${RED}❌ Cannot connect to K8s cluster${NC}"
    echo "   Check your kubeconfig"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 4. Check SSH access to nodes
echo -e "${BLUE}4. Checking SSH access to nodes...${NC}"
NODES=("192.168.1.74" "192.168.1.75" "192.168.1.77")
for NODE in "${NODES[@]}"; do
    if ssh -o ConnectTimeout=5 -o BatchMode=yes root@$NODE "echo 'SSH OK'" &>/dev/null; then
        echo -e "${GREEN}✅ SSH access to $NODE OK${NC}"
    else
        echo -e "${RED}❌ Cannot SSH to root@$NODE${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# 5. Check Docker
echo -e "${BLUE}5. Checking Docker...${NC}"
if docker info &>/dev/null; then
    echo -e "${GREEN}✅ Docker daemon is running${NC}"
    
    # Check Docker Hub login
    if docker info 2>/dev/null | grep -q "Username"; then
        USERNAME=$(docker info 2>/dev/null | grep "Username" | awk '{print $2}')
        echo -e "${GREEN}✅ Logged in to Docker Hub as: $USERNAME${NC}"
    else
        echo -e "${YELLOW}⚠️  Not logged in to Docker Hub${NC}"
        echo "   Run: docker login"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${RED}❌ Docker daemon is NOT running${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 6. Check K8s files
echo -e "${BLUE}6. Checking K8s configuration files...${NC}"
check_file "k8s/00-namespace.yaml"
check_file "k8s/02-config/configmap.yaml"

# Check secrets
if [ -f "k8s/02-config/secrets.yaml" ]; then
    echo -e "${GREEN}✅ secrets.yaml exists${NC}"
    
    # Check if it's still the example
    if grep -q "CHANGE_ME" k8s/02-config/secrets.yaml; then
        echo -e "${YELLOW}   ⚠️  secrets.yaml contains default values!${NC}"
        echo "   Please update all passwords and API keys"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    if [ -f "k8s/02-config/secrets.yaml.example" ]; then
        echo -e "${YELLOW}⚠️  secrets.yaml NOT found (but example exists)${NC}"
        echo "   Run: cp k8s/02-config/secrets.yaml.example k8s/02-config/secrets.yaml"
        echo "   Then edit the file with your actual values"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${RED}❌ Neither secrets.yaml nor secrets.yaml.example found${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi
echo ""

# 7. Check .env file for reference
echo -e "${BLUE}7. Checking environment files...${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ .env file exists (for reference)${NC}"
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "   You'll need to know your API keys for secrets.yaml"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Summary:${NC}"
echo -e "Errors:   $ERRORS"
echo -e "Warnings: $WARNINGS"
echo ""

if [ $ERRORS -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}✅ All checks passed! Ready to deploy.${NC}"
    else
        echo -e "${YELLOW}⚠️  Some warnings found, but you can proceed.${NC}"
    fi
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. ./scripts/01-setup-nfs.sh        # Setup NFS storage"
    echo "2. ./scripts/02-build-push.sh       # Build and push Docker image"
    echo "3. ./scripts/03-deploy-all.sh       # Deploy to K8s"
else
    echo -e "${RED}❌ Some errors found. Please fix them before proceeding.${NC}"
    exit 1
fi