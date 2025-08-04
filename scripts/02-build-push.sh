#!/bin/bash
# scripts/02-build-push.sh
# Build và push Docker images từ cấu trúc hiện tại

set -e

# Configuration
DOCKER_REGISTRY="krntl"  # Thay đổi thành registry của bạn
APP_NAME="hgcb"
VERSION="v2.0"
PLATFORMS="linux/amd64"  # Thêm ,linux/arm64 nếu cần

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🐳 Building and pushing Docker images...${NC}"

# 1. Check if we're in the right directory
if [ ! -f "requirements.txt" ] || [ ! -d "app" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# 2. Check Docker login
echo -e "${YELLOW}Checking Docker login status...${NC}"
if ! docker info 2>/dev/null | grep -q "Username"; then
    echo -e "${RED}Not logged in to Docker Hub. Please login:${NC}"
    docker login
fi

# 3. Choose Dockerfile
DOCKERFILE="Dockerfile.k8s"
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${YELLOW}Dockerfile.k8s not found, using default Dockerfile${NC}"
    DOCKERFILE="Dockerfile"
fi

# 4. Enable Docker buildx (for multi-platform builds)
echo -e "${YELLOW}Setting up Docker buildx...${NC}"
docker buildx create --name multibuilder --use 2>/dev/null || docker buildx use multibuilder
docker buildx inspect --bootstrap

# 5. Build and push main application
echo -e "${GREEN}Building $APP_NAME:$VERSION using $DOCKERFILE...${NC}"

# Build với buildx cho multi-platform từ current directory
docker buildx build \
    --platform=$PLATFORMS \
    --tag $DOCKER_REGISTRY/$APP_NAME:$VERSION \
    --tag $DOCKER_REGISTRY/$APP_NAME:latest \
    --push \
    --file $DOCKERFILE \
    .

# 6. Verify image
echo -e "${YELLOW}Verifying pushed image...${NC}"
docker pull $DOCKER_REGISTRY/$APP_NAME:$VERSION
docker images | grep $APP_NAME

# 7. Update K8s deployment files với image mới
echo -e "${YELLOW}Updating K8s deployment files...${NC}"
if [ -f "k8s/04-apps/chatbot-deployment.yaml" ]; then
    sed -i.bak "s|image: .*hgcb:.*|image: $DOCKER_REGISTRY/$APP_NAME:$VERSION|g" k8s/04-apps/chatbot-deployment.yaml
    rm k8s/04-apps/chatbot-deployment.yaml.bak
    echo -e "${GREEN}Updated deployment file with new image${NC}"
fi

# 8. Clean up
echo -e "${YELLOW}Cleaning up...${NC}"
docker buildx prune -f

echo -e "${GREEN}✅ Docker image built and pushed successfully!${NC}"
echo -e "Image: ${YELLOW}$DOCKER_REGISTRY/$APP_NAME:$VERSION${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update secrets: vim k8s/02-config/secrets.yaml"
echo "2. Deploy to K8s: ./scripts/03-deploy-all.sh"