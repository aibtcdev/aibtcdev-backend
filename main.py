import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# set up a simple app to respond to server health check
app = FastAPI()
routes_initialized = False

# setup CORS origins
# TODO: use after confirming it works
cors_origins = [
    "https://sprint.aibtc.dev",
    "https://aibtcdev-frontend.replit.app",
]


# setup middleware to allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    return {"message": "A healthy server is a happy server!"}


@app.get("/init")
async def initialize():
    global routes_initialized

    if not routes_initialized:
        # load env vars and init langtrace
        load_dotenv()
        from langtrace_python_sdk import langtrace

        langtrace.init()
        # load crew endpoints and initialize routes
        from api import crew

        app.include_router(crew.router)
        # set global flag to prevent reinitialization
        routes_initialized = True
        return {"message": "Routes loaded and initialized!"}
    return {"message": "Routes already initialized!"}
