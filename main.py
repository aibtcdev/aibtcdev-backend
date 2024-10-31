import asyncio
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import crew
from api import chat

# set up a simple app to respond to server health check
pass_health_check = FastAPI()


@pass_health_check.get("/")
async def health():
    return {"message": "A healthy server is a happy server!"}


root_router = APIRouter()


@root_router.get("/")
async def root():
    return {"message": "CrewAI execution API is running!"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # sleep to let health check complete
    await asyncio.sleep(10)
    # load the routes
    app.include_router(root_router)
    app.include_router(crew.router)
    app.include_router(chat.router)
    yield
    # can add cleanup code here


app = FastAPI(lifespan=lifespan)

# Allow requests from the Next.js frontend
# For local dev: allow_orgins=["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aibtcdev-frontend.replit.app",
        "https://sprint.aibtc.dev",
        "*",
    ],  # Allow access from frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)
