from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from .database import messages_collection, users_collection
import logging

router = APIRouter()
logger = logging.getLogger("uvicorn")

class Message(BaseModel):
    sender_email: str
    receiver_username: str
    content: str
    timestamp: Optional[datetime] = None

@router.post("/send")
def send_message(message: Message):
    """
    Sends a message from one user to another.
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
        msg_data["sender_id"] = sender["_id"] # Store internal ID for efficiency
        msg_data["receiver_id"] = receiver["_id"]
        
        messages_collection.insert_one(msg_data)
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