import runpod
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging
import platform

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for model (loaded once per container)
model = None
tokenizer = None

def load_model():
    """Load model and tokenizer - called once per container startup"""
    global model, tokenizer
    
    try:
        model_name = "deepseek-ai/deepseek-coder-6.7b-instruct"

        # Try any of these alternatives:
        # model_name = "codellama/CodeLlama-7b-Instruct-hf"
        # model_name = "WizardLM/WizardCoder-Python-7B-V1.0"
        # model_name = "Phind/Phind-CodeLlama-34B-v2"  # Larger, better quality
        
        logger.info(f"Loading model: {model_name}")
        logger.info(f"PyTorch version: {torch.__version__}")
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True
        )
        
        # Check if we're on Mac or have CUDA available
        device_map = "auto" if torch.cuda.is_available() else None
        
        # Use appropriate dtype for PyTorch 2.6.0
        if torch.cuda.is_available():
            torch_dtype = torch.float16
        else:
            # For CPU on Mac, use float32 for better compatibility
            torch_dtype = torch.float32
        
        # Configure quantization only if bitsandbytes is available and we have CUDA
        quantization_config = None
        if torch.cuda.is_available():
            try:
                from transformers import BitsAndBytesConfig
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True
                )
                logger.info("Using 4-bit quantization")
            except ImportError:
                logger.info("BitsAndBytes not available, loading without quantization")
        
        # Load model with PyTorch 2.6.0 optimizations
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=quantization_config,
            device_map=device_map,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True  # Better memory management in newer PyTorch
        )
        
        logger.info(f"Model loaded successfully on {platform.system()}!")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        logger.info(f"Model device: {next(model.parameters()).device}")
        return True
        
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        return False

def handler(event):
    """RunPod serverless handler function"""
    global model, tokenizer
    
    try:
        # Load model if not already loaded
        if model is None or tokenizer is None:
            success = load_model()
            if not success:
                return {
                    "error": "Failed to load model",
                    "status": "error"
                }
        
        # Parse input
        input_data = event.get("input", {})
        message = input_data.get("message", "")
        context = input_data.get("context", "")
        max_length = input_data.get("max_length", 512)
        
        if not message:
            return {
                "error": "No message provided",
                "status": "error"
            }
        
        # Format prompt for code explanation
        prompt = f"""You are a helpful assistant that explains code and app features to non-technical users in simple terms.

Context from codebase:
{context}

User Question: {message}

Please provide a clear, simple explanation without technical jargon:"""

        # Tokenize input
        inputs = tokenizer.encode(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048
        )
        
        # Move to appropriate device
        device = next(model.parameters()).device
        inputs = inputs.to(device)
        
        # Generate response with PyTorch 2.6.0 optimizations
        with torch.no_grad():
            outputs = model.generate(
                inputs,
                max_length=inputs.shape[1] + min(max_length, 512),
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.1,
                use_cache=True  # Better caching in newer versions
            )
        
        # Decode response
        response = tokenizer.decode(
            outputs[0][inputs.shape[1]:],
            skip_special_tokens=True
        ).strip()
        
        # Clean up response
        if not response:
            response = "I apologize, but I couldn't generate a proper response. Could you please rephrase your question?"
        
        return {
            "response": response,
            "status": "success",
            "tokens_used": len(outputs[0]),
            "device_used": str(device),
            "pytorch_version": torch.__version__
        }
        
    except Exception as e:
        logger.error(f"Handler error: {str(e)}")
        return {
            "error": str(e),
            "status": "error"
        }

if __name__ == "__main__":
    # Start the RunPod serverless worker
    runpod.serverless.start({
        "handler": handler,
        "return_aggregate_stream": True
    })