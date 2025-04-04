import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import api
from api import chat, tools, webhooks
from config import config
from lib.logger import configure_logger
from services import startup
from services.websocket import websocket_manager

# Configure module logger
logger = configure_logger(__name__)

# Define app
app = FastAPI(
    title="AI BTC Dev Backend",
    description="Backend API for AI BTC Dev services",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sprint.aibtc.dev",
        "https://sprint-faster.aibtc.dev",
        "https://*.aibtcdev-frontend.pages.dev",  # Cloudflare preview deployments
        "http://localhost:3000",  # Local development
        "https://staging.aibtc.chat",
        "https://app.aibtc.dev",
        "https://aibtc.dev",
        "https://app-staging.aibtc.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Simple health check endpoint
@app.get("/")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy"}


# Load API routes
app.include_router(api.tools.router)
app.include_router(api.chat.router)
app.include_router(api.webhooks.router)


@app.on_event("startup")
async def startup_event():
    """Run startup tasks."""
    # Start the WebSocket manager's cleanup task
    # Note: This is now redundant as startup.run() will also start the WebSocket manager
    # but we'll keep it for clarity and to ensure it's started early
    asyncio.create_task(websocket_manager.start_cleanup_task())

    # Run other startup tasks
    await startup.run()


@app.on_event("shutdown")
async def shutdown_event():
    """Run shutdown tasks."""
    logger.info("Shutting down FastAPI application")
    await startup.shutdown()
