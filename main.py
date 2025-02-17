from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from api import chat, tools, webhooks
from config import config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from lib.logger import configure_logger
from services.startup import init_background_tasks, shutdown

# Configure module logger
logger = configure_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    try:
        await init_background_tasks()
        logger.info("Background tasks initialized")
        yield
    finally:
        await shutdown()


app = FastAPI(lifespan=lifespan)

# Setup CORS origins
cors_origins = [
    "https://sprint.aibtc.dev",
    "https://sprint-faster.aibtc.dev",
    "https://*.aibtcdev-frontend.pages.dev",  # Cloudflare preview deployments
    "http://localhost:3000",  # Local development
    "https://staging.aibtc.chat",
    "https://app.aibtc.dev",
    "https://aibtc.dev",
    "https://app-staging.aibtc.dev",
]

# Setup middleware to allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


# Lightweight health check endpoint
@app.get("/")
async def health():
    return {"status": "healthy"}


app.include_router(tools.router)
app.include_router(chat.router)
app.include_router(webhooks.router)
