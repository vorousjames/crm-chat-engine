FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

# Copy requirements and handler
COPY requirements.txt handler.py ./

# Upgrade pip first
RUN pip install --upgrade pip

# Install PyTorch 2.6.0 with CUDA 11.8 (compatible with base image)
RUN pip install torch==2.6.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install other Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables for RunPod
ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_CACHE=/runpod-volume
ENV HF_HOME=/runpod-volume

# Set the command
CMD ["python", "handler.py"]