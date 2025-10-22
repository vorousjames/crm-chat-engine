import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

# Verify PyTorch 2.6.0 specific features
if torch.__version__.startswith('2.6'):
    print("✅ PyTorch 2.6.0 detected - enhanced features available")
else:
    print(f"⚠️  Expected PyTorch 2.6.x, got {torch.__version__}")

try:
    from transformers import AutoTokenizer
    print("✅ Transformers imported successfully")
except ImportError as e:
    print(f"❌ Transformers import error: {e}")

try:
    import runpod
    print("✅ RunPod imported successfully")
except ImportError as e:
    print(f"❌ RunPod import error: {e}")

try:
    from transformers import BitsAndBytesConfig
    print("✅ BitsAndBytes available for quantization")
except ImportError as e:
    print(f"⚠️  BitsAndBytes not available: {e}")

if torch.cuda.is_available():
    print(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
    print(f"📊 GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
else:
    print("💻 Running on CPU")