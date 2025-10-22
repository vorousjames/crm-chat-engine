import sys
import os
sys.path.append(os.path.dirname(__file__))

from handler import handler
import json

def test_local():
    """Test the handler locally"""
    
    print("Testing handler locally...")
    
    # Test with code context
    test_event = {
        "input": {
            "message": "What does this function do?",
            "context": """
def authenticate_user(username, password):
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None
            """,
            "max_length": 256
        }
    }
    
    print("Running inference...")
    result = handler(test_event)
    print("Result:")
    print(json.dumps(result, indent=2))
    
    # Test without context
    simple_test = {
        "input": {
            "message": "How do I reset my password?",
            "context": "",
            "max_length": 200
        }
    }
    
    print("\nTesting simple question...")
    simple_result = handler(simple_test)
    print("Simple Result:")
    print(json.dumps(simple_result, indent=2))

if __name__ == "__main__":
    test_local()