from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .db import sessions_collection

app = FastAPI()

# Allow CORS for all origins (customize in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        # Get last message timestamp if available
        last_msg = s.get("messages", [])[-1] if s.get("messages") else None
        last_updated = last_msg.get("timestamp") if last_msg else None
        session_list.append({
            "session_id": s["session_id"],
            "last_updated": last_updated
        })
    # Sort by last_updated descending (most recent first)
    session_list.sort(key=lambda x: x["last_updated"] or 0, reverse=True)
    return {"sessions": session_list} 