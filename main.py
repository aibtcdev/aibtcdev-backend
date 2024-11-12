from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import asyncio

# Set up a simple app to respond to server health check
app = FastAPI()
routes_initialized = False
routes_initializing = False  # New flag to indicate initialization in progress
initialization_lock = asyncio.Lock()  # Lock to ensure single initialization

# Setup CORS origins
cors_origins = [
    "https://sprint.aibtc.dev",
    "https://aibtcdev-frontend.replit.app",
]

# Setup middleware to allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Lightweight health check endpoint
@app.get("/")
async def health():
    # Check if routes are already initialized
    if routes_initialized:
        return {"status": "healthy"}

    # If routes are still initializing, return a "starting" status
    if routes_initializing:
        return {"status": "starting"}

    # If neither initialized nor initializing, start initialization in a background task
    loop = asyncio.get_event_loop()
    loop.create_task(initialize_routes())
    return {"status": "starting"}  # Indicate server is in the process of starting up


# Background initialization function with lock to prevent re-entry
async def initialize_routes():
    global routes_initialized, routes_initializing

    # Only allow one task to initialize at a time
    async with initialization_lock:
        # Double-check in case initialization happened while waiting for the lock
        if not routes_initialized:
            routes_initializing = True  # Set initializing status

            load_dotenv()

            # # Lazy import and initialize langtrace
            # from langtrace_python_sdk import langtrace

            # langtrace.init()

            # Import and set up routes from 'crew'
            from api import crew
            from api import public_crews

            from api import chat
            from api import metrics
            app.include_router(crew.router)
            app.include_router(public_crews.router)
            app.include_router(chat.router)
            app.include_router(metrics.router)

            # Mark routes as initialized
            routes_initialized = True
            routes_initializing = False  # Clear initializing flag
