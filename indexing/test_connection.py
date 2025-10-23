#!/usr/bin/env python3

import os
import weaviate
import weaviate.auth as wv_auth
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.production')

def test_weaviate_connection():
    """Test connection to Weaviate Cloud"""
    
    weaviate_url = os.getenv('WEAVIATE_URL')
    weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
    
    print(f"🔗 Testing connection to: {weaviate_url}")
    print(f"🔑 Using API key: {weaviate_api_key[:8]}...{weaviate_api_key[-4:] if len(weaviate_api_key) > 12 else '***'}")
    
    if not weaviate_url or not weaviate_api_key:
        print("❌ Missing WEAVIATE_URL or WEAVIATE_API_KEY")
        return False
    
    if weaviate_api_key == 'your-actual-weaviate-api-key-here':
        print("❌ Please update WEAVIATE_API_KEY in .env.production")
        return False
    
    try:
        # Try different authentication methods
        print("🧪 Attempting connection with API key auth...")
        
        client = weaviate.Client(
            url=weaviate_url,
            auth_client_secret=wv_auth.AuthApiKey(api_key=weaviate_api_key),
            timeout_config=(10, 30)
        )
        
        # Test the connection
        meta = client.get_meta()
        print(f"✅ Connected successfully!")
        print(f"   Weaviate version: {meta.get('version', 'Unknown')}")
        print(f"   Modules: {meta.get('modules', {}).keys()}")
        
        # Test schema access
        schema = client.schema.get()
        classes = [cls['class'] for cls in schema.get('classes', [])]
        print(f"   Existing classes: {classes}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        
        # Try alternative connection method
        print("🧪 Trying alternative connection method...")
        try:
            client = weaviate.Client(
                url=weaviate_url,
                auth_client_secret=weaviate.AuthApiKey(api_key=weaviate_api_key)
            )
            meta = client.get_meta()
            print(f"✅ Alternative connection successful!")
            print(f"   Version: {meta.get('version', 'Unknown')}")
            return True
        except Exception as e2:
            print(f"❌ Alternative connection also failed: {e2}")
        
        return False

if __name__ == "__main__":
    print("🧪 Testing Weaviate Cloud Connection")
    print("=" * 40)
    
    success = test_weaviate_connection()
    
    if success:
        print("\n🎉 Connection test passed! You can now run the indexing.")
        print("Run: python3 handler.py")
    else:
        print("\n💡 Connection troubleshooting:")
        print("1. Verify your API key is correct")
        print("2. Check if your Weaviate cluster is running")
        print("3. Ensure your cluster allows API key authentication")
        print("4. Try regenerating your API key in Weaviate Console")
