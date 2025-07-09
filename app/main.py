from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.db import sessions_collection  # adjust this if outside app/
import httpx

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Auto session saving during chat ===
@app.post("/api/message")
async def receive_message(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    user_message = data.get("message")

    if not session_id or not user_message:
        return {"error": "Missing session_id or message"}

    try:
        async with httpx.AsyncClient() as client:
            rasa_response = await client.post(
                "http://localhost:5005/webhooks/rest/webhook",  # or use EC2 IP
                json={"sender": session_id, "message": user_message["text"]},
                timeout=10,
            )
        rasa_data = rasa_response.json()
    except Exception as e:
        return {"error": f"Failed to contact Rasa: {str(e)}"}

    # Combine user and bot messages
    full_chat = []
    full_chat.append({
        "text": user_message["text"],
        "sender": "user",
        "timestamp": user_message["timestamp"]
    })

    for bot_msg in rasa_data:
        full_chat.append({
            "text": bot_msg.get("text", ""),
            "sender": "bot",
            "timestamp": user_message["timestamp"] + 1,
            "buttons": bot_msg.get("buttons"),
            "image": bot_msg.get("image"),
        })

    # Save to MongoDB
    sessions_collection.update_one(
        {"session_id": session_id},
        {"$push": {"messages": {"$each": full_chat}}},
        upsert=True
    )

    return {"success": True, "responses": rasa_data}

# === Manual session saving (already present) ===
@app.post("/save-session")
async def save_session(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    messages = data.get("messages")
    if not session_id or messages is None:
        return {"success": False, "error": "Missing session_id or messages"}
    sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"messages": messages}},
        upsert=True
    )
    return {"success": True}

@app.get("/get-session/{session_id}")
def get_session(session_id: str):
    session = sessions_collection.find_one({"session_id": session_id})
    if not session:
        return {"success": False, "error": "Session not found"}
    return {"success": True, "messages": session["messages"]}

@app.get("/list-sessions")
def list_sessions():
    sessions = sessions_collection.find({}, {"session_id": 1, "messages": 1, "_id": 0})
    session_list = []
    for s in sessions:
        last_msg = s.get("messages", [])[-1] if s.get("messages") else None
        last_updated = last_msg.get("timestamp") if last_msg else None
        session_list.append({
            "session_id": s["session_id"],
            "last_updated": last_updated
        })
    session_list.sort(key=lambda x: x["last_updated"] or 0, reverse=True)
    return {"sessions": session_list}
