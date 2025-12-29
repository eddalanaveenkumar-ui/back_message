from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel
from typing import List, Optional
from .database import users_collection, connections_collection
import logging

router = APIRouter()
logger = logging.getLogger("uvicorn")

class UserConnectionRequest(BaseModel):
    email: str
    username: str
    display_name: Optional[str] = None
    photo_url: Optional[str] = None

class UserSearchResponse(BaseModel):
    username: str
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    is_following: bool = False

@router.post("/connect")
def connect_to_messaging(request: UserConnectionRequest):
    """
    Enables the messaging service for a user by adding them to the messaging database.
    """
    try:
        user_data = request.dict()
        users_collection.update_one(
            {"email": request.email},
            {"$set": user_data},
            upsert=True
        )
        return {"status": "Connected to messaging server"}
    except Exception as e:
        logger.error(f"Error connecting user: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to messaging server")

@router.get("/search")
def search_users(q: str = Query(..., min_length=1), current_user_email: Optional[str] = None):
    """
    Searches for users by username or display name.
    """
    try:
        users = list(users_collection.find(
            {
                "$or": [
                    {"username": {"$regex": q, "$options": "i"}},
                    {"display_name": {"$regex": q, "$options": "i"}}
                ]
            },
            {"_id": 0}
        ).limit(20))
        
        # Add is_following status if current_user_email is provided
        if current_user_email:
            current_user = users_collection.find_one({"email": current_user_email})
            if current_user:
                for user in users:
                    is_following = connections_collection.find_one({
                        "user_id": current_user["_id"],
                        "follows_id": user["username"] # Assuming username is unique identifier for now
                    })
                    user["is_following"] = bool(is_following)

        return users
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

@router.get("/profile/{username}")
def get_user_profile(username: str, current_user_email: Optional[str] = None):
    """
    Gets a user's public profile with follower/following counts.
    """
    try:
        user = users_collection.find_one({"username": username}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Get counts
        # Followers: connections where follows_id == username
        followers_count = connections_collection.count_documents({"follows_id": username})
        
        # Following: connections where user_id == user's internal ID
        # We need the internal ID for this query
        user_internal = users_collection.find_one({"username": username})
        following_count = connections_collection.count_documents({"user_id": user_internal["_id"]})
        
        user["followers_count"] = followers_count
        user["following_count"] = following_count
        
        # Check if current user is following this profile
        if current_user_email:
            current_user = users_collection.find_one({"email": current_user_email})
            if current_user:
                is_following = connections_collection.find_one({
                    "user_id": current_user["_id"],
                    "follows_id": username
                })
                user["is_following"] = bool(is_following)
        
        return user
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch profile")

@router.post("/follow")
def follow_user(data: dict = Body(...)):
    """
    Follows a user.
    """
    follower_email = data.get("follower_email")
    following_username = data.get("following_username")
    
    if not follower_email or not following_username:
        raise HTTPException(status_code=400, detail="Missing follower_email or following_username")

    try:
        follower = users_collection.find_one({"email": follower_email})
        if not follower:
             raise HTTPException(status_code=404, detail="Follower not found")

        connections_collection.update_one(
            {"user_id": follower["_id"], "follows_id": following_username},
            {"$set": {"timestamp": 1}}, # Placeholder timestamp
            upsert=True
        )
        return {"status": "Followed successfully"}
    except Exception as e:
        logger.error(f"Error following user: {e}")
        raise HTTPException(status_code=500, detail="Failed to follow user")

@router.post("/unfollow")
def unfollow_user(data: dict = Body(...)):
    """
    Unfollows a user.
    """
    follower_email = data.get("follower_email")
    following_username = data.get("following_username")

    if not follower_email or not following_username:
        raise HTTPException(status_code=400, detail="Missing follower_email or following_username")

    try:
        follower = users_collection.find_one({"email": follower_email})
        if not follower:
             raise HTTPException(status_code=404, detail="Follower not found")

        connections_collection.delete_one(
            {"user_id": follower["_id"], "follows_id": following_username}
        )
        return {"status": "Unfollowed successfully"}
    except Exception as e:
        logger.error(f"Error unfollowing user: {e}")
        raise HTTPException(status_code=500, detail="Failed to unfollow user")