from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import tools, webhooks, agent_lookup, profiles, dao
from app.config import config
from app.lib.logger import configure_logger

# Configure module logger
logger = configure_logger(__name__)

_ = config

# Define app
app = FastAPI(
    title="AI BTC Dev Backend",
    description="Backend API for AI BTC Dev services",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https://((sprint|sprint-faster|app|app-staging)\.aibtc\.dev|aibtc\.dev|staging\.aibtc\.chat|[^.]+\.aibtcdev-frontend(-staging)?\.pages\.dev)|http://localhost:3000)$",
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
app.include_router(agent_lookup.router, prefix="/api")
app.include_router(profiles.router, prefix="/api/profiles")
app.include_router(dao.router, prefix="/api/dao")



@app.on_event("startup")
async def startup_event():
    """Run web server startup tasks."""
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
