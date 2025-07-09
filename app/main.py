from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx  # HTTP client to call Rasa server
from .session_manager import session_manager

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RASA_WEBHOOK_URL = "http://51.20.18.59/webhooks/rest/webhook"  # Rasa running locally

@app.post("/api/message")
async def receive_message(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    message = data.get("message")

    if not session_id or not message:
        return {"error": "Missing session_id or message"}

    # 1. Track message for idle timeout
    session_manager.add_message(session_id, message)

    # 2. Send to Rasa
    try:
        async with httpx.AsyncClient() as client:
            rasa_response = await client.post(
                RASA_WEBHOOK_URL,
                json={
                    "sender": session_id,
                    "message": message["text"]
                },
                timeout=10
            )
        rasa_data = rasa_response.json()
    except Exception as e:
        return {"error": f"Failed to contact Rasa: {str(e)}"}

    # 3. Add Rasa bot replies to session manager
    for bot_msg in rasa_data:
        session_manager.add_message(session_id, {
            "text": bot_msg.get("text", ""),
            "sender": "bot",
            "timestamp": int(message["timestamp"]) + 1,  # Just add 1s to simulate reply time
            "buttons": bot_msg.get("buttons"),
            "image": bot_msg.get("image"),
        })

    # 4. Return Rasa reply to frontend
    return {"success": True, "responses": rasa_data}
