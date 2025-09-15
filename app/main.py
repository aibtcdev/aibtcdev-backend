from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agents, daos, tools, webhooks, profiles
from app.config import config
from app.lib.logger import configure_logger, setup_uvicorn_logging
from app.middleware.logging import LoggingMiddleware

# Configure module logger
logger = configure_logger(__name__)

_ = config

# Define app
app = FastAPI(
    title="AI BTC Dev Backend",
    description="Backend API for AI BTC Dev services",
    version="0.1.0",
)

# Add logging middleware first
app.add_middleware(LoggingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(?:https://(?:aibtc\.dev|[^.]+\.aibtc\.dev|aibtc\.com|[^.]+\.aibtc\.com|[^.]+\.aibtcdev-frontend(?:-staging)?\.pages\.dev)|http://localhost:3000)$",
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
app.include_router(tools.router)
app.include_router(webhooks.router)
app.include_router(agents.router)
app.include_router(profiles.router)
app.include_router(daos.router)


@app.on_event("startup")
async def startup_event():
    """Run web server startup tasks."""
    # Configure JSON logging after uvicorn is fully initialized
    setup_uvicorn_logging()

    logger.info("Starting FastAPI web server...")
    # Background services (job runners, bot, etc.) are handled by worker.py
    logger.info("Web server startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Run web server shutdown tasks."""
    logger.info("Shutting down FastAPI web server...")
    # Only handle web server specific cleanup
    # Background services shutdown is handled by worker.py
    logger.info("Web server shutdown complete")
