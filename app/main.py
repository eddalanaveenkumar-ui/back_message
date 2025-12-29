from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from . import user_routes, chat_routes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

app = FastAPI(title="Triangle Messaging Backend")

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routers ---
app.include_router(user_routes.router, prefix="/api", tags=["User"])
app.include_router(chat_routes.router, prefix="/api", tags=["Chat"])


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "Triangle Messaging Backend is running"}