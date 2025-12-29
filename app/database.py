from pymongo import MongoClient
import os

# Use environment variables for sensitive data
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "triangle_messaging")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

# Collections
users_collection = db["users"]
connections_collection = db["connections"]
messages_collection = db["messages"]

def create_indexes():
    users_collection.create_index("email", unique=True)
    users_collection.create_index("username", unique=True)
    connections_collection.create_index([("user_id", 1), ("follows_id", 1)], unique=True)
    messages_collection.create_index([("sender_id", 1), ("receiver_id", 1)])
    messages_collection.create_index("timestamp")

# Initialize indexes on startup
create_indexes()