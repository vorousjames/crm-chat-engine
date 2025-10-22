#!/bin/bash

# Deploy script for RunPod Serverless

set -e

echo "Building Docker image..."

# Build the image
docker build -t crm-chat-engine:latest .

# Tag for Docker Hub (replace with your username)
DOCKER_USERNAME=${1:-"your-dockerhub-username"}
IMAGE_NAME="$DOCKER_USERNAME/crm-chat-engine:latest"

echo "Tagging image as $IMAGE_NAME"
docker tag crm-chat-engine:latest $IMAGE_NAME

echo "Pushing to Docker Hub..."
docker push $IMAGE_NAME

echo "Image pushed successfully!"
echo "Use this image in RunPod: $IMAGE_NAME"

echo ""
echo "Next steps:"
echo "1. Go to https://runpod.io"
echo "2. Navigate to Serverless > Templates"
echo "3. Create new template with image: $IMAGE_NAME"
echo "4. Deploy as serverless endpoint"