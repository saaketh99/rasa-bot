from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from db import client
from bson import ObjectId
from fastapi.encoders import jsonable_encoder
import time

app = FastAPI()

db = client["orders-db"]
conversations_collection = db["user_sessions"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a new conversation (first user message)
@app.post("/conversations")
async def create_conversation(request: Request):
    data = await request.json()
    first_message = data.get("message")
    if not first_message:
        return {"success": False, "error": "Missing first message"}
    now = int(time.time() * 1000)
    conversation = {
        "title": first_message.get("text", "New Conversation"),
        "created_at": now,
        "updated_at": now,
        "messages": [first_message],
    }
    result = conversations_collection.insert_one(conversation)
    return {"success": True, "conversation_id": str(result.inserted_id)}

# Append a message to a conversation
@app.post("/conversations/{conversation_id}/messages")
async def append_message(conversation_id: str, request: Request):
    data = await request.json()
    message = data.get("message")
    if not message:
        return {"success": False, "error": "Missing message"}
    now = int(time.time() * 1000)
    result = conversations_collection.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$push": {"messages": message}, "$set": {"updated_at": now}}
    )
    if result.matched_count == 0:
        return {"success": False, "error": "Conversation not found"}
    return {"success": True}

# List all conversations (id, title, created_at, updated_at)
@app.get("/conversations")
def list_conversations():
    conversations = conversations_collection.find({}, {"title": 1, "created_at": 1, "updated_at": 1})
    return {"conversations": [
        {"id": str(c["_id"]), "title": c.get("title", "Untitled"), "created_at": c.get("created_at"), "updated_at": c.get("updated_at")}
        for c in conversations
    ]}

# Get a conversation by ID
@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    c = conversations_collection.find_one({"_id": ObjectId(conversation_id)})
    if not c:
        return {"success": False, "error": "Conversation not found"}
    c["id"] = str(c["_id"])
    del c["_id"]
    return jsonable_encoder(c) 