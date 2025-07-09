import time
from threading import Thread, Lock
from .db import sessions_collection  # import the MongoDB collection

SESSION_TIMEOUT_SECONDS = 300  # 5 minutes

class SessionManager:
    def __init__(self):
        self.sessions = {}  # {session_id: {"messages": [...], "last_active": timestamp}}
        self.lock = Lock()
        self.monitor_thread = Thread(target=self.monitor_idle_sessions, daemon=True)
        self.monitor_thread.start()

    def add_message(self, session_id, message):
        with self.lock:
            session = self.sessions.get(session_id, {"messages": [], "last_active": time.time()})
            session["messages"].append(message)
            session["last_active"] = time.time()
            self.sessions[session_id] = session

    def monitor_idle_sessions(self):
        while True:
            time.sleep(60)
            now = time.time()
            with self.lock:
                expired_sessions = [
                    sid for sid, s in self.sessions.items()
                    if now - s["last_active"] > SESSION_TIMEOUT_SECONDS
                ]
                for sid in expired_sessions:
                    print(f"Saving session {sid} to MongoDB due to timeout.")
                    sessions_collection.insert_one({
                        "session_id": sid,
                        "messages": self.sessions[sid]["messages"],
                        "saved_at": time.time()
                    })
                    del self.sessions[sid]

    # ✅ ADD THIS METHOD for /save-session route
    def store_session(self, session_id, messages):
        sessions_collection.insert_one({
            "session_id": session_id,
            "messages": messages,
            "saved_at": time.time()
        })

# Global instance
session_manager = SessionManager()
