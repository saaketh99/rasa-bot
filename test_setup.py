import requests
import json
import time

def test_fastapi():
    """Test FastAPI backend"""
    try:
        response = requests.get("http://localhost:8000/conversations")
        if response.status_code == 200:
            print("✅ FastAPI Backend: Working")
            return True
        else:
            print(f"❌ FastAPI Backend: Error {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FastAPI Backend: Connection failed - {e}")
        return False

def test_mock_rasa():
    """Test Mock Rasa server"""
    try:
        # Test health endpoint
        response = requests.get("http://localhost:5005/health")
        if response.status_code == 200:
            print("✅ Mock Rasa Server: Health check passed")
        else:
            print(f"❌ Mock Rasa Server: Health check failed - {response.status_code}")
            return False
        
        # Test webhook endpoint
        data = {"sender": "test", "message": "hello"}
        response = requests.post("http://localhost:5005/webhooks/rest/webhook", json=data)
        if response.status_code == 200:
            result = response.json()
            if result and len(result) > 0:
                print("✅ Mock Rasa Server: Webhook working")
                return True
            else:
                print("❌ Mock Rasa Server: Webhook returned empty response")
                return False
        else:
            print(f"❌ Mock Rasa Server: Webhook failed - {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Mock Rasa Server: Connection failed - {e}")
        return False

def test_frontend():
    """Test Frontend (basic connectivity)"""
    try:
        response = requests.get("http://localhost:3000")
        if response.status_code == 200:
            print("✅ Frontend: Accessible")
            return True
        else:
            print(f"❌ Frontend: Error {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend: Connection failed - {e}")
        return False

def test_full_conversation():
    """Test a full conversation flow"""
    try:
        # Create conversation
        message_data = {
            "message": {
                "id": "test-1",
                "text": "Hello, can you help me track my order?",
                "sender": "user",
                "timestamp": int(time.time() * 1000)
            }
        }
        
        response = requests.post("http://localhost:8000/conversations", json=message_data)
        if response.status_code == 200:
            result = response.json()
            conversation_id = result.get("conversation_id")
            print(f"✅ Conversation created: {conversation_id}")
            
            # Test Rasa response
            rasa_data = {
                "sender": conversation_id,
                "message": "Hello, can you help me track my order?"
            }
            
            rasa_response = requests.post("http://localhost:5005/webhooks/rest/webhook", json=rasa_data)
            if rasa_response.status_code == 200:
                rasa_result = rasa_response.json()
                if rasa_result and len(rasa_result) > 0:
                    bot_message = rasa_result[0].get("text", "")
                    print(f"✅ Bot response: {bot_message}")
                    return True
                else:
                    print("❌ Bot response empty")
                    return False
            else:
                print(f"❌ Rasa webhook failed: {rasa_response.status_code}")
                return False
        else:
            print(f"❌ Conversation creation failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Full conversation test failed: {e}")
        return False

def main():
    print("🔍 Testing Rasa Chatbot Setup...")
    print("=" * 50)
    
    tests = [
        ("FastAPI Backend", test_fastapi),
        ("Mock Rasa Server", test_mock_rasa),
        ("Frontend", test_frontend),
        ("Full Conversation Flow", test_full_conversation)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Testing {test_name}...")
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! Your chatbot is ready to use.")
        print("🌐 Access the frontend at: http://localhost:3000")
    else:
        print("⚠️  Some tests failed. Please check the services.")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 