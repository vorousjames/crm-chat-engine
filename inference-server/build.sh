#!/bin/bash

# Build script for RunPod inference server with PyTorch 2.6.0

set -e

echo "🚀 Building CRM Chat Inference Server with PyTorch 2.6.0..."

# Configuration
IMAGE_NAME="crm-chat-inference"
DOCKER_USERNAME=${1:-"yourdockerhub"}  # Pass your Docker Hub username as first argument
FULL_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME:latest"

# Change to inference-server directory
cd "$(dirname "$0")"

echo "📋 Build Configuration:"
echo "  PyTorch Version: 2.6.0"
echo "  Target Image: $FULL_IMAGE_NAME"
echo ""

echo "Available Dockerfile options:"
echo "1. Dockerfile (RunPod base - recommended)"  
echo "2. Dockerfile.nvidia (NVIDIA CUDA base)"
echo "3. Dockerfile.simple (Python slim base)"
echo ""

read -p "Choose Dockerfile (1-3) or press Enter for default (1): " choice
choice=${choice:-1}

case $choice in
    1)
        DOCKERFILE="Dockerfile"
        echo "Using RunPod base image"
        ;;
    2) 
        DOCKERFILE="Dockerfile.nvidia"
        echo "Using NVIDIA CUDA base image"
        ;;
    3)
        DOCKERFILE="Dockerfile.simple" 
        echo "Using Python slim base image"
        ;;
    *)
        echo "Invalid choice, using default Dockerfile"
        DOCKERFILE="Dockerfile"
        ;;
esac

echo ""

# Build the Docker image
echo "🔨 Building Docker image with $DOCKERFILE..."
docker build -f $DOCKERFILE -t $IMAGE_NAME .

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    
    # Tag for Docker Hub
    echo "🏷️  Tagging for Docker Hub..."
    docker tag $IMAGE_NAME $FULL_IMAGE_NAME
    
    echo ""
    echo "🎉 Build completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Push to Docker Hub: docker push $FULL_IMAGE_NAME"
    echo "2. Use in RunPod with image: $FULL_IMAGE_NAME"
    echo ""
    echo "RunPod Template Settings:"
    echo "  - Container Disk: 30GB"
    echo "  - GPU: RTX A5000 or better"
    echo "  - Environment Variables:"
    echo "    TRANSFORMERS_CACHE=/runpod-volume"
    echo "    HF_HOME=/runpod-volume"
    echo ""
    
    # Optional: Test the image locally
    read -p "Test the image locally? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🧪 Testing image locally..."
        docker run --rm -it $IMAGE_NAME python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print('✅ Image test successful!')
"
    fi
    
else
    echo "❌ Build failed!"
    echo "Check the logs above for errors."
    exit 1
fi
