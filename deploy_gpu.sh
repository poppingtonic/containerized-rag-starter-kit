#!/bin/bash

# Deploy GraphRAG with GPU acceleration

echo "Deploying GPU-accelerated GraphRAG processor..."

# Check for NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-smi not found. Please install NVIDIA drivers."
    exit 1
fi

# Check for NVIDIA Docker runtime
if ! docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "ERROR: NVIDIA Docker runtime not working. Please install nvidia-docker2."
    echo "See: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    exit 1
fi

# Show GPU info
echo "GPU detected:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# Deploy with GPU support
echo "Starting deployment..."
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up -d

echo ""
echo "Deployment complete! GraphRAG processor is running with GPU acceleration."
echo ""
echo "Monitor logs with:"
echo "  docker compose logs -f graphrag-processor"
echo ""
echo "Check GPU usage with:"
echo "  nvidia-smi -l 1"