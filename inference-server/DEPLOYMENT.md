# RunPod Deployment Guide - PyTorch 2.6.0

## Build and Deploy

### 1. Build the Docker Image
```bash
./build.sh your-dockerhub-username
```

### 2. Push to Docker Hub
```bash
docker push your-dockerhub-username/crm-chat-inference:latest
```

### 3. Create RunPod Template
1. Go to [RunPod Console](https://runpod.io)
2. Navigate to **Serverless > Templates**
3. Click **New Template**

**Template Settings:**
- **Container Image:** `your-dockerhub-username/crm-chat-inference:latest`
- **Container Disk:** 30 GB
- **Volume Disk:** 10 GB (optional)
- **GPU Type:** RTX A5000 or better

**Environment Variables:**
```
TRANSFORMERS_CACHE=/runpod-volume
HF_HOME=/runpod-volume
```

### 4. Deploy Endpoint
1. Go to **Serverless > Endpoints**
2. Click **New Endpoint**
3. Select your template
4. Configure:
   - **Min Workers:** 0
   - **Max Workers:** 3
   - **Idle Timeout:** 5 seconds
   - **Execution Timeout:** 300 seconds

### 5. Test the Endpoint

**Request Format:**
```json
{
  "input": {
    "message": "How do I reset my password?",
    "context": "User authentication features...",
    "max_length": 400
  }
}
```

**Expected Response:**
```json
{
  "status": "COMPLETED",
  "output": {
    "response": "To reset your password...",
    "status": "success",
    "tokens_used": 156,
    "device_used": "cuda:0",
    "pytorch_version": "2.6.0"
  }
}
```

## Configuration for Chat Server

Update your Heroku chat server environment:

```bash
heroku config:set RUNPOD_ENDPOINT_URL=https://api.runpod.ai/v2/YOUR-ENDPOINT-ID/runsync
heroku config:set RUNPOD_API_KEY=your-runpod-api-key
heroku config:set USE_LOCAL_INFERENCE=false
```

## Key Features

✅ **PyTorch 2.6.0** - Latest features and optimizations
✅ **CUDA 12.1** - Compatible GPU acceleration  
✅ **4-bit Quantization** - Memory efficient inference
✅ **DeepSeek Coder 6.7B** - Specialized code understanding model
✅ **Auto-scaling** - Scales to zero when not in use

## Troubleshooting

### Build Issues
- Ensure Docker is running
- Check your Docker Hub credentials
- Verify internet connection for base image download

### RunPod Issues  
- Check endpoint logs in RunPod console
- Verify GPU availability in your region
- Ensure sufficient credits/payment method

### Performance Issues
- Consider RTX A6000 or A100 for better performance
- Increase execution timeout for complex queries
- Monitor GPU memory usage in logs
