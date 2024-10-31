from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import crew
from api import chat

app = FastAPI()

# Allow requests from the Next.js frontend
# For local dev: allow_orgins=["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aibtcdev-frontend.replit.app",
        "https://sprint.aibtc.dev",
        "*"
    ],  # Allow access from frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Include the crew routes
app.include_router(crew.router)

# Include the chat routes
app.include_router(chat.router)


@app.get("/")
async def root():
    return {"message": "CrewAI execution API is running!"}
