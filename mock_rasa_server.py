from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import time

app = Flask(__name__)
CORS(app)

# Mock responses for different types of queries
MOCK_RESPONSES = {
    "greet": "Hello! How can I help you with your orders today?",
    "goodbye": "Goodbye! Have a great day!",
    "order_track": "I found your order. It's currently in transit and expected to be delivered within 2-3 business days.",
    "customer_orders": "I found 5 orders for that customer in the specified date range. Would you like me to show you the details?",
    "route_orders": "I found 12 orders between those locations. The most recent one was shipped yesterday.",
    "status_orders": "I found 8 orders with that status. Would you like me to list them for you?",
    "default": "I understand you're asking about orders. Could you please provide more specific details like an order ID, customer name, or date range?"
}

@app.route('/webhooks/rest/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        sender = data.get('sender', 'user')
        message = data.get('message', '').lower()
        
        # Simple intent detection
        if any(word in message for word in ['hello', 'hi', 'hey']):
            response_text = MOCK_RESPONSES['greet']
        elif any(word in message for word in ['bye', 'goodbye', 'see you']):
            response_text = MOCK_RESPONSES['goodbye']
        elif any(word in message for word in ['track', 'order', 'status']) and any(word in message for word in ['wkft', 'ola', 'order']):
            response_text = MOCK_RESPONSES['order_track']
        elif any(word in message for word in ['customer', 'wakefit', 'ola', 'amazon']):
            response_text = MOCK_RESPONSES['customer_orders']
        elif any(word in message for word in ['from', 'to', 'route', 'between']):
            response_text = MOCK_RESPONSES['route_orders']
        elif any(word in message for word in ['delivered', 'pending', 'transit']):
            response_text = MOCK_RESPONSES['status_orders']
        else:
            response_text = MOCK_RESPONSES['default']
        
        response = {
            "recipient_id": sender,
            "text": response_text
        }
        
        return jsonify([response])
    
    except Exception as e:
        print(f"Error in webhook: {e}")
        return jsonify([{
            "recipient_id": sender,
            "text": "Sorry, I encountered an error. Please try again."
        }])

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "message": "Mock Rasa server is running"})

if __name__ == '__main__':
    print("Starting Mock Rasa Server on port 5005...")
    print("This is a temporary solution until the real Rasa server is available.")
    app.run(host='0.0.0.0', port=5005, debug=True) 