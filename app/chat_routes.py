from fastapi import APIRouter, HTTPException, Body, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from .database import messages_collection, users_collection
import logging
import json

router = APIRouter()
logger = logging.getLogger("uvicorn")

class Message(BaseModel):
    sender_email: str
    receiver_username: str
    content: str # This will be the encrypted message
    timestamp: Optional[datetime] = None

# --- Connection Manager for WebSockets ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]

    async def send_personal_message(self, message: str, username: str):
        if username in self.active_connections:
            await self.active_connections[username].send_text(message)

manager = ConnectionManager()

# --- WebSocket Endpoint ---
@router.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(username, websocket)
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(username)

# --- HTTP Routes ---
@router.post("/send")
async def send_message(message: Message):
    """
    Sends a message from one user to another and forwards it via WebSocket if the receiver is connected.
    """
    try:
        sender = users_collection.find_one({"email": message.sender_email})
        if not sender:
            raise HTTPException(status_code=404, detail="Sender not found")
            
        receiver = users_collection.find_one({"username": message.receiver_username})
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiver not found")

        msg_data = message.dict()
        msg_data["timestamp"] = datetime.utcnow()
        msg_data["sender_id"] = sender["_id"]
        msg_data["receiver_id"] = receiver["_id"]
        
        messages_collection.insert_one(msg_data)
        
        # Forward the message via WebSocket to the receiver
        # The message sent includes the sender's username for the client
        await manager.send_personal_message(
            json.dumps({
                "sender_username": sender["username"],
                "content": message.content,
                "timestamp": msg_data["timestamp"].isoformat()
            }),
            message.receiver_username
        )

        return {"status": "Message sent"}
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

@router.get("/history")
def get_chat_history(user1_email: str, user2_username: str, limit: int = 50):
    """
    Retrieves the chat history between two users.
    """
    try:
        user1 = users_collection.find_one({"email": user1_email})
        user2 = users_collection.find_one({"username": user2_username})
        
        if not user1 or not user2:
            raise HTTPException(status_code=404, detail="User not found")

        messages = list(messages_collection.find(
            {
                "$or": [
                    {"sender_id": user1["_id"], "receiver_id": user2["_id"]},
                    {"sender_id": user2["_id"], "receiver_id": user1["_id"]}
                ]
            },
            {"_id": 0, "sender_id": 0, "receiver_id": 0} # Exclude internal IDs from response
        ).sort("timestamp", 1).limit(limit))
        
        # Add sender username to each message for frontend convenience
        for msg in messages:
            if msg.get("sender_email") == user1_email:
                msg["is_me"] = True
            else:
                msg["is_me"] = False

        return messages
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")

@router.get("/conversations")
def get_conversations(email: str):
    """
    Returns a list of users the current user has chatted with, along with the last message.
    """
    try:
        current_user = users_collection.find_one({"email": email})
        if not current_user:
            raise HTTPException(status_code=404, detail="User not found")
            
        current_user_id = current_user["_id"]

        # Aggregation pipeline to find unique conversation partners and last message
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"sender_id": current_user_id},
                        {"receiver_id": current_user_id}
                    ]
                }
            },
            {
                "$sort": {"timestamp": -1}
            },
            {
                "$group": {
                    "_id": {
                        "$cond": [
                            {"$eq": ["$sender_id", current_user_id]},
                            "$receiver_id",
                            "$sender_id"
                        ]
                    },
                    "last_message": {"$first": "$content"},
                    "timestamp": {"$first": "$timestamp"}
                }
            },
            {
                "$sort": {"timestamp": -1}
            }
        ]

        conversations = list(messages_collection.aggregate(pipeline))
        
        result = []
        for convo in conversations:
            partner_id = convo["_id"]
            partner = users_collection.find_one({"_id": partner_id}, {"_id": 0, "username": 1, "photo_url": 1})
            
            if partner:
                result.append({
                    "username": partner["username"],
                    "photo_url": partner.get("photo_url"),
                    "last_message": convo["last_message"],
                    "timestamp": convo["timestamp"]
                })
                
        return result

    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")