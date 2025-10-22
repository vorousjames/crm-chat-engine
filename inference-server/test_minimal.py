import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

try:
    from transformers import AutoTokenizer
    print("Transformers imported successfully")
except ImportError as e:
    print(f"Transformers import error: {e}")

try:
    import runpod
    print("RunPod imported successfully")
except ImportError as e:
    print(f"RunPod import error: {e}")