#!/bin/bash
# scripts/03-deploy-all.sh
# Deploy toàn bộ hệ thống lên K8s từ cấu trúc hiện tại

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if we're in the right directory
if [ ! -f "requirements.txt" ] || [ ! -d "app" ] || [ ! -d "k8s" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    echo "Current directory: $(pwd)"
    exit 1
fi

# Function to wait for deployment
wait_for_deployment() {
    local name=$1
    local namespace=$2
    echo -e "${YELLOW}Waiting for $name to be ready...${NC}"
    kubectl wait --for=condition=available --timeout=300s deployment/$name -n $namespace 2>/dev/null || true
    kubectl wait --for=condition=ready pod -l app=$name -n $namespace --timeout=300s 2>/dev/null || true
}

# Function to wait for statefulset
wait_for_statefulset() {
    local name=$1
    local namespace=$2
    echo -e "${YELLOW}Waiting for $name to be ready...${NC}"
    kubectl rollout status statefulset/$name -n $namespace --timeout=300s
}

echo -e "${GREEN}🚀 Deploying HG Chatbot to Kubernetes...${NC}"
echo -e "${BLUE}Project root: $(pwd)${NC}"

# 1. Pre-flight checks
echo -e "${BLUE}1. Running pre-flight checks...${NC}"

# Check kubectl connection
if ! kubectl cluster-info &>/dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster!${NC}"
    echo "Please check your kubeconfig"
    exit 1
fi

# Check if required files exist
if [ ! -f "k8s/02-config/secrets.yaml" ]; then
    echo -e "${RED}❌ k8s/02-config/secrets.yaml not found!${NC}"
    echo "Please create it from template or example"
    exit 1
fi

# Check if model weights exist
if [ ! -d "model_weights" ] || [ -z "$(ls -A model_weights)" ]; then
    echo -e "${YELLOW}⚠️  Warning: model_weights directory is empty${NC}"
    echo "Make sure to copy model files to NFS after deployment"
fi

# Check if namespace exists
if kubectl get namespace hg-chatbot &>/dev/null; then
    echo -e "${YELLOW}⚠️  Namespace 'hg-chatbot' already exists${NC}"
    read -p "Do you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 2. Create namespace
echo -e "${BLUE}2. Creating namespace...${NC}"
kubectl apply -f k8s/00-namespace.yaml

# 3. Deploy storage resources
echo -e "${BLUE}3. Deploying storage resources...${NC}"
if [ -d "k8s/01-storage" ]; then
    kubectl apply -f k8s/01-storage/
    sleep 5
else
    echo -e "${YELLOW}Storage config directory not found, skipping...${NC}"
fi

# 4. Deploy configurations
echo -e "${BLUE}4. Deploying configurations...${NC}"
kubectl apply -f k8s/02-config/

# 5. Deploy databases
echo -e "${BLUE}5. Deploying databases...${NC}"
kubectl apply -f k8s/03-databases/

# Wait for databases to be ready
wait_for_statefulset "mongodb" "hg-chatbot"
wait_for_statefulset "qdrant" "hg-chatbot"
wait_for_statefulset "postgres" "hg-chatbot"

# 6. Copy model weights to NFS (if setup)
echo -e "${BLUE}6. Checking model weights on NFS...${NC}"
if [ -d "model_weights" ] && [ ! -z "$(ls -A model_weights)" ]; then
    echo -e "${YELLOW}Found local model weights. Please ensure they are copied to NFS:${NC}"
    echo "  scp -r model_weights/* root@192.168.1.74:/srv/k8s-shared/model-weights/"
    read -p "Have you copied the model weights to NFS? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Please copy model weights before continuing${NC}"
        exit 1
    fi
fi

# 7. Initialize databases
echo -e "${BLUE}7. Initializing databases...${NC}"
# MongoDB user creation
echo "Creating MongoDB user..."
kubectl exec -n hg-chatbot mongodb-0 -- mongosh --quiet --eval "
    use admin;
    db.createUser({
        user: 'hgchatbot',
        pwd: 'your_mongo_user_password',
        roles: [{role: 'readWrite', db: 'hg_chatbot'}]
    });
" 2>/dev/null || echo "MongoDB user might already exist"

# 8. Deploy applications
echo -e "${BLUE}8. Deploying applications...${NC}"
kubectl apply -f k8s/04-apps/

# Wait for main app
wait_for_deployment "hg-chatbot" "hg-chatbot"
wait_for_deployment "crawl-comment" "hg-chatbot"

# 9. Deploy ingress (if needed)
if [ -f "k8s/05-ingress/ingress.yaml" ]; then
    echo -e "${BLUE}9. Deploying ingress...${NC}"
    kubectl apply -f k8s/05-ingress/
fi

# 10. Show deployment status
echo -e "${BLUE}10. Deployment Status:${NC}"
echo ""
kubectl get all -n hg-chatbot
echo ""

# 11. Get service endpoints
echo -e "${GREEN}✅ Deployment completed!${NC}"
echo ""
echo -e "${BLUE}Service Access:${NC}"

# Get NodePort
NODE_PORT=$(kubectl get svc hg-chatbot-service -n hg-chatbot -o jsonpath='{.spec.ports[0].nodePort}')
echo -e "NodePort: ${YELLOW}http://<any-node-ip>:$NODE_PORT${NC}"
echo -e "Example URLs:"
echo -e "  - ${YELLOW}http://192.168.1.74:$NODE_PORT${NC} (Master)"
echo -e "  - ${YELLOW}http://192.168.1.75:$NODE_PORT${NC} (Worker 1)"
echo -e "  - ${YELLOW}http://192.168.1.77:$NODE_PORT${NC} (Worker 2)"

# Get LoadBalancer IP (if applicable)
LB_IP=$(kubectl get svc hg-chatbot-service -n hg-chatbot -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
if [ ! -z "$LB_IP" ]; then
    echo -e "LoadBalancer: ${YELLOW}http://$LB_IP${NC}"
fi

echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "• View logs: kubectl logs -f deployment/hg-chatbot -n hg-chatbot"
echo "• Scale app: kubectl scale deployment hg-chatbot --replicas=3 -n hg-chatbot"
echo "• Port forward: kubectl port-forward svc/hg-chatbot-service 8888:80 -n hg-chatbot"
echo "• Check pods: kubectl get pods -n hg-chatbot"
echo "• Exec into pod: kubectl exec -it deployment/hg-chatbot -n hg-chatbot -- bash"

# 12. Quick health check
echo ""
echo -e "${BLUE}Running health check in 15 seconds...${NC}"
sleep 15

# Check if service is responding
if [ ! -z "$NODE_PORT" ]; then
    HEALTH_CHECK_URL="http://192.168.1.74:$NODE_PORT/health"
    echo -e "Checking: $HEALTH_CHECK_URL"
    
    if curl -s -o /dev/null -w "%{http_code}" $HEALTH_CHECK_URL | grep -q "200"; then
        echo -e "${GREEN}✅ Health check passed!${NC}"
    else
        echo -e "${YELLOW}⚠️  Health check failed. Service might still be starting up.${NC}"
        echo "Check logs with: kubectl logs -f deployment/hg-chatbot -n hg-chatbot"
    fi
fi

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"