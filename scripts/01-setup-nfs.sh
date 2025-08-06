#!/bin/bash
# scripts/01-setup-nfs.sh
# Setup NFS server và mount cho các nodes

set -e

echo "🔧 Setting up NFS Server and Clients..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
NFS_SERVER_IP="192.168.1.74"
NFS_BASE_PATH="/srv/k8s-shared"
WORKER_IPS=("192.168.1.75" "192.168.1.77")

# Check if we have model_weights locally
LOCAL_MODEL_WEIGHTS="./model_weights"

# Function to run commands on remote hosts
run_remote() {
    local host=$1
    local cmd=$2
    echo -e "${YELLOW}Running on $host: $cmd${NC}"
    ssh root@$host "$cmd"
}

# 1. Setup NFS Server (on master node)
echo -e "${GREEN}1. Setting up NFS Server on $NFS_SERVER_IP${NC}"
cat << 'EOF' | ssh root@$NFS_SERVER_IP bash
    # Install NFS server
    apt-get update
    apt-get install -y nfs-kernel-server

    # Create directories
    mkdir -p /srv/k8s-shared/{uploaded-files,model-weights,logs}
    
    # Set permissions
    chown -R nobody:nogroup /srv/k8s-shared
    chmod -R 777 /srv/k8s-shared/uploaded-files
    chmod -R 755 /srv/k8s-shared/model-weights  # Read-only for model weights
    chmod -R 777 /srv/k8s-shared/logs

    # Configure exports
    cat > /etc/exports << EOL
# HG Chatbot NFS Shares
/srv/k8s-shared/uploaded-files 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
/srv/k8s-shared/model-weights 192.168.1.0/24(ro,sync,no_subtree_check,no_root_squash)
/srv/k8s-shared/logs 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
EOL

    # Apply exports
    exportfs -ra
    systemctl restart nfs-kernel-server
    systemctl enable nfs-kernel-server

    # Show exports
    echo "NFS exports configured:"
    exportfs -v
    
    echo "NFS Server setup completed!"
EOF

# 2. Setup NFS Clients on all nodes (including master for testing)
echo -e "${GREEN}2. Setting up NFS Clients on all nodes${NC}"
ALL_IPS=("$NFS_SERVER_IP" "${WORKER_IPS[@]}")

for NODE_IP in "${ALL_IPS[@]}"; do
    echo -e "${YELLOW}Configuring NFS client on $NODE_IP${NC}"
    cat << 'EOF' | ssh root@$NODE_IP bash
        # Install NFS client
        apt-get update
        apt-get install -y nfs-common

        # Create mount points
        mkdir -p /mnt/k8s-shared/{uploaded-files,model-weights,logs}

        # Unmount if already mounted
        umount /mnt/k8s-shared/uploaded-files 2>/dev/null || true
        umount /mnt/k8s-shared/model-weights 2>/dev/null || true
        umount /mnt/k8s-shared/logs 2>/dev/null || true

        # Remove old fstab entries
        sed -i '/k8s-shared/d' /etc/fstab

        # Add to fstab for persistent mount
        cat >> /etc/fstab << EOL
# HG Chatbot NFS Mounts
192.168.1.74:/srv/k8s-shared/uploaded-files /mnt/k8s-shared/uploaded-files nfs defaults,_netdev 0 0
192.168.1.74:/srv/k8s-shared/model-weights /mnt/k8s-shared/model-weights nfs defaults,ro,_netdev 0 0
192.168.1.74:/srv/k8s-shared/logs /mnt/k8s-shared/logs nfs defaults,_netdev 0 0
EOL

        # Mount all
        mount -a

        # Verify mounts
        echo "Mounted filesystems:"
        df -h | grep k8s-shared
        
        echo "NFS Client setup completed on $(hostname)!"
EOF
done

# 3. Copy model weights to NFS (if available locally)
echo -e "${GREEN}3. Handling model weights...${NC}"
if [ -d "$LOCAL_MODEL_WEIGHTS" ] && [ ! -z "$(ls -A $LOCAL_MODEL_WEIGHTS 2>/dev/null)" ]; then
    echo "Found local model_weights directory. Copying to NFS..."
    
    # Get size of model weights
    MODEL_SIZE=$(du -sh $LOCAL_MODEL_WEIGHTS | cut -f1)
    echo -e "${YELLOW}Model weights size: $MODEL_SIZE${NC}"
    
    # Copy with progress
    echo "Copying files..."
    rsync -avP --stats $LOCAL_MODEL_WEIGHTS/ root@$NFS_SERVER_IP:/srv/k8s-shared/model-weights/
    
    echo -e "${GREEN}Model weights copied successfully!${NC}"
else
    echo -e "${YELLOW}No local model_weights found or directory is empty.${NC}"
    echo -e "${YELLOW}Please manually copy model files to:${NC}"
    echo "  $NFS_SERVER_IP:/srv/k8s-shared/model-weights/"
    echo ""
    echo "Example command:"
    echo "  scp -r /path/to/model_weights/* root@$NFS_SERVER_IP:/srv/k8s-shared/model-weights/"
fi

# 4. Create test files
echo -e "${GREEN}4. Creating test files...${NC}"
run_remote $NFS_SERVER_IP "echo 'NFS test successful' > /srv/k8s-shared/uploaded-files/nfs-test.txt"
run_remote $NFS_SERVER_IP "echo 'Model weights directory ready' > /srv/k8s-shared/model-weights/README.txt"

# 5. Verify setup from all nodes
echo -e "${GREEN}5. Verifying NFS setup from all nodes...${NC}"
for NODE_IP in "${WORKER_IPS[@]}"; do
    echo -e "${YELLOW}Testing from $NODE_IP:${NC}"
    run_remote $NODE_IP "ls -la /mnt/k8s-shared/uploaded-files/nfs-test.txt"
    run_remote $NODE_IP "cat /mnt/k8s-shared/uploaded-files/nfs-test.txt"
done

# 6. Show summary
echo ""
echo -e "${GREEN}✅ NFS setup completed successfully!${NC}"
echo ""
echo -e "${BLUE}NFS Shares Summary:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 Uploaded Files: $NFS_SERVER_IP:/srv/k8s-shared/uploaded-files (Read/Write)"
echo "🤖 Model Weights:  $NFS_SERVER_IP:/srv/k8s-shared/model-weights (Read Only)"
echo "📝 Logs:          $NFS_SERVER_IP:/srv/k8s-shared/logs (Read/Write)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if model weights were copied
if ssh root@$NFS_SERVER_IP "ls -A /srv/k8s-shared/model-weights/*.bin 2>/dev/null || ls -A /srv/k8s-shared/model-weights/*.pt 2>/dev/null" &>/dev/null; then
    echo -e "${GREEN}✅ Model weights found in NFS share${NC}"
else
    echo -e "${YELLOW}⚠️  No model weights found in NFS share${NC}"
    echo "   Please copy them manually before deploying the application"
fi