import weaviate
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import json

load_dotenv()

def test_weaviate_connection():
    """Test connection to Weaviate"""
    try:
        client = weaviate.Client("http://localhost:8080")
        meta = client.get_meta()
        print("✅ Weaviate connection successful!")
        print(f"   Version: {meta.get('version', 'Unknown')}")
        return client
    except Exception as e:
        print(f"❌ Weaviate connection failed: {e}")
        return None

def test_embedding_model():
    """Test sentence transformer model"""
    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
        test_embedding = model.encode("How do I login to the app?")
        print(f"✅ Embedding model loaded successfully!")
        print(f"   Embedding dimension: {len(test_embedding)}")
        return True
    except Exception as e:
        print(f"❌ Embedding model failed: {e}")
        return False

def test_schema(client):
    """Test if schema exists"""
    try:
        schema = client.schema.get()
        classes = [cls['class'] for cls in schema.get('classes', [])]
        print(f"✅ Schema retrieved successfully!")
        print(f"   Available classes: {classes}")
        
        if 'AppFeature' in classes:
            print("✅ AppFeature class found!")
            
            # Get class details
            app_feature_class = next(cls for cls in schema['classes'] if cls['class'] == 'AppFeature')
            properties = [prop['name'] for prop in app_feature_class['properties']]
            print(f"   Properties: {properties}")
            
        else:
            print("⚠️  AppFeature class not found")
        
        return True
    except Exception as e:
        print(f"❌ Schema test failed: {e}")
        return False

def test_feature_search(client):
    """Test searching indexed features"""
    try:
        result = client.query.get(
            "AppFeature", 
            ["featureDescription", "userBenefit", "featureType", "userActions"]
        ).with_limit(5).do()
        
        features = result.get('data', {}).get('Get', {}).get('AppFeature', [])
        
        print(f"✅ Found {len(features)} app features in database")
        
        if features:
            # Group by feature type
            feature_types = {}
            for feature in features:
                ftype = feature.get('featureType', 'unknown')
                feature_types[ftype] = feature_types.get(ftype, 0) + 1
            
            print(f"   Feature types found: {feature_types}")
            
            # Show examples
            for i, feature in enumerate(features[:3]):
                print(f"\n   --- Feature {i+1} ---")
                print(f"   Type: {feature.get('featureType', 'Unknown')}")
                print(f"   Description: {feature.get('featureDescription', 'No description')}")
                print(f"   User Benefit: {feature.get('userBenefit', 'No benefit listed')}")
                print(f"   Actions: {feature.get('userActions', 'No actions listed')[:80]}...")
        
        return len(features) > 0
    except Exception as e:
        print(f"❌ Feature search test failed: {e}")
        return False

def test_user_queries(client):
    """Test semantic search with user-style questions"""
    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Test user questions
        user_questions = [
            "How do I sign into my account?",
            "Can I edit my profile information?",
            "How do I search for something?",
            "Is there a way to export my data?",
            "How do I change my settings?",
            "What can I do on the main page?"
        ]
        
        print("\n🔍 Testing user questions:")
        
        for question in user_questions:
            # Generate query embedding
            query_embedding = model.encode(question)
            
            # Search for relevant features
            result = client.query.get(
                "AppFeature",
                ["featureDescription", "userBenefit", "featureType", "userActions"]
            ).with_near_vector({
                "vector": query_embedding.tolist()
            }).with_limit(2).do()
            
            features = result.get('data', {}).get('Get', {}).get('AppFeature', [])
            
            print(f"\n   Q: '{question}'")
            if features:
                for feature in features:
                    print(f"   → Feature: {feature.get('featureDescription', 'Unknown')}")
                    print(f"     Benefit: {feature.get('userBenefit', 'No benefit')[:60]}...")
                    print(f"     Actions: {feature.get('userActions', 'No actions')[:60]}...")
            else:
                print(f"   → No relevant features found")
        
        return True
    except Exception as e:
        print(f"❌ User query test failed: {e}")
        return False

def get_feature_stats(client):
    """Get feature database statistics"""
    try:
        # Count total features
        result = client.query.aggregate("AppFeature").with_meta_count().do()
        total_count = result['data']['Aggregate']['AppFeature'][0]['meta']['count']
        
        # Get feature type distribution
        result = client.query.aggregate("AppFeature").with_fields("featureType").with_group_by(["featureType"]).do()
        
        print(f"\n📊 Feature Database Statistics:")
        print(f"   Total indexed features: {total_count}")
        
        groups = result.get('data', {}).get('Aggregate', {}).get('AppFeature', [])
        if groups:
            print(f"   Feature type distribution:")
            for group in groups:
                ftype = group.get('groupedBy', {}).get('value', 'unknown')
                count = group.get('meta', {}).get('count', 0)
                print(f"     {ftype.replace('_', ' ').title()}: {count} features")
        
        return True
    except Exception as e:
        print(f"❌ Stats retrieval failed: {e}")
        return False

def show_example_responses(client):
    """Show example chatbot responses"""
    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("\n💬 Example Chatbot Responses:")
        print("="*50)
        
        example_query = "How do I update my information?"
        query_embedding = model.encode(example_query)
        
        result = client.query.get(
            "AppFeature",
            ["featureDescription", "userBenefit", "userActions", "relatedFeatures"]
        ).with_near_vector({
            "vector": query_embedding.tolist()
        }).with_limit(2).do()
        
        features = result.get('data', {}).get('Get', {}).get('AppFeature', [])
        
        print(f"User Question: '{example_query}'")
        print("\nChatbot Response:")
        print("Based on your app's features, here's how you can update your information:")
        
        if features:
            for i, feature in enumerate(features):
                print(f"\n{i+1}. {feature.get('featureDescription', 'Feature')}")
                print(f"   What you can do: {feature.get('userActions', 'Various actions')}")
                print(f"   Why it helps: {feature.get('userBenefit', 'Helps you stay organized')}")
                
                related = feature.get('relatedFeatures', '')
                if related:
                    print(f"   Related features: {related}")
        else:
            print("I'd be happy to help! Let me search for relevant features...")
        
        return True
    except Exception as e:
        print(f"❌ Example response failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing User-Focused Feature Indexing...\n")
    
    # Test embedding model
    if not test_embedding_model():
        print("Fix embedding model issues before proceeding")
        exit(1)
    
    print("\n" + "="*50 + "\n")
    
    # Test Weaviate connection
    client = test_weaviate_connection()
    if not client:
        print("Fix Weaviate connection before proceeding")
        exit(1)
    
    print("\n" + "="*50 + "\n")
    
    # Test schema
    if not test_schema(client):
        print("Run the indexing script to create schema")
        exit(1)
    
    print("\n" + "="*50 + "\n")
    
    # Test feature search
    if test_feature_search(client):
        print("\n" + "="*50 + "\n")
        get_feature_stats(client)
        print("\n" + "="*50 + "\n")
        test_user_queries(client)
        print("\n" + "="*50 + "\n")
        show_example_responses(client)
    else:
        print("Run the indexing script to populate feature database")
    
    print("\n✅ All tests completed!")
    print("\nYour feature database is ready to help users understand what they can do with your app! 🎉")