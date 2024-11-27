from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from api import crew
from api import public_crews
from api import public_stats
from api import chat
from api import metrics
from services.cron import execute_cron_job
import asyncio
from services.bot import start_application
import logging

logger = logging.getLogger(__name__)

load_dotenv()

scheduler = AsyncIOScheduler()
scheduler.add_job(execute_cron_job, "interval", hours=1)
scheduler.start()

app = FastAPI()

# Setup CORS origins
cors_origins = [
    "https://sprint.aibtc.dev",
    "https://sprint-faster.aibtc.dev",
    "http://localhost:3000",  # Development environment
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


async def start_bot():
    """Start the Telegram bot in the background."""
    try:
        application = await start_application()
        return application
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        raise


@app.on_event("startup")
async def startup_event():
    """Start the bot when the FastAPI application starts."""
    asyncio.create_task(start_bot())


# Lightweight health check endpoint
@app.get("/")
async def health():
    return {"status": "healthy"}


app.include_router(crew.router)
app.include_router(public_crews.router)
app.include_router(public_stats.router)
app.include_router(chat.router)
app.include_router(metrics.router)
