from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from app.api import tools, webhooks
from app.config import config
from app.lib.logger import configure_logger

# Configure module logger
logger = configure_logger(__name__)

_ = config

# Enhanced FastAPI app with comprehensive OpenAPI metadata
app = FastAPI(
    title="AI BTC Dev Backend API",
    description="""
    ## AI BTC Dev Backend API

    A sophisticated FastAPI backend powering AI-driven Stacks blockchain DAO management and trading capabilities.

    ### Features

    * **🏛️ DAO Management**: Create, vote on, and manage DAO proposals with AI enhancement
    * **💰 Trading & Finance**: Execute DEX trades and manage wallets
    * **🧠 AI Analysis**: Generate proposal recommendations and comprehensive evaluations
    * **🔗 Blockchain Integration**: Native Stacks blockchain operations
    * **🛠️ Developer Tools**: Dynamic tool discovery and social integrations

    ### Authentication

    All endpoints require authentication using:
    - **Bearer Token**: `Authorization: Bearer <token>`
    - **API Key**: `X-API-Key: <api_key>`

    ### Networks

    - **Testnet**: Development and testing environment
    - **Mainnet**: Production environment with real transactions

    ---

    **⚠️ Disclaimer**: This is alpha software. Use at your own risk. 
    aibtc.dev is not liable for any lost, locked, or mistakenly sent funds.
    """,
    version="1.0.0",
    terms_of_service="https://aibtc.dev/terms",
    contact={
        "name": "AI BTC Dev Team",
        "url": "https://aibtc.dev",
        "email": "support@aibtc.dev",
    },
    license_info={
        "name": "MIT License",
        "url": "https://github.com/aibtcdev/aibtcdev-backend/blob/main/LICENSE",
    },
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and system status endpoints",
        },
        {
            "name": "tool-discovery",
            "description": "Discover and search available tools in the system",
        },
        {
            "name": "faktory",
            "description": "Trading operations on Faktory DEX including token purchases and faucet funding",
        },
        {
            "name": "dao",
            "description": "DAO management including proposal creation, voting, and AI-powered recommendations",
        },
        {
            "name": "agent-account",
            "description": "Agent account management and contract approvals",
        },
        {
            "name": "wallet",
            "description": "Wallet operations including testnet faucet funding",
        },
        {
            "name": "evaluation",
            "description": "AI-powered proposal evaluation and analysis",
        },
        {
            "name": "social",
            "description": "Social media integrations including Twitter/X embedding",
        },
        {
            "name": "webhooks",
            "description": "Blockchain event processing and DAO creation webhooks",
        },
    ],
    servers=[
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://api.aibtc.dev", "description": "Production server"},
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https://((sprint|sprint-faster|app|app-staging)\.aibtc\.dev|aibtc\.dev|staging\.aibtc\.chat|[^.]+\.aibtcdev-frontend(-staging)?\.pages\.dev)|http://localhost:3000)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    """Generate custom OpenAPI schema with enhanced documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )

    # Add custom schema enhancements
    openapi_schema["info"]["x-logo"] = {"url": "https://aibtc.dev/logo.png"}

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your bearer token in the format: Bearer <token>",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Enter your API key",
        },
    }

    # Apply security to all endpoints by default
    openapi_schema["security"] = [{"BearerAuth": []}, {"ApiKeyAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Enhanced health check endpoint with proper documentation
@app.get(
    "/",
    tags=["health"],
    summary="Health Check",
    description="Simple health check endpoint to verify the API is running",
    responses={
        200: {
            "description": "API is healthy and running",
            "content": {"application/json": {"example": {"status": "healthy"}}},
        }
    },
)
async def health_check():
    """
    Simple health check endpoint.

    Returns a status message indicating the API is running properly.
    This endpoint does not require authentication.
    """
    return {"status": "healthy"}


# Custom Swagger UI with enhanced styling
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with enhanced styling and configuration."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Interactive API Documentation",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css",
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "operationsSorter": "method",
            "filter": True,
            "showExtensions": True,
            "showCommonExtensions": True,
        },
    )


# Export OpenAPI JSON endpoint
@app.get(
    "/openapi/export",
    tags=["health"],
    summary="Export OpenAPI Schema",
    description="Download the complete OpenAPI schema as JSON",
    responses={
        200: {
            "description": "OpenAPI schema in JSON format",
            "content": {
                "application/json": {
                    "example": {
                        "openapi": "3.1.0",
                        "info": {"title": "AI BTC Dev Backend API", "version": "1.0.0"},
                    }
                }
            },
        }
    },
)
async def export_openapi_schema():
    """
    Export the complete OpenAPI schema.

    Returns the full OpenAPI 3.1.0 specification for this API,
    which can be used with other tools or for offline documentation.
    """
    return app.openapi()


# Load API routes
app.include_router(tools.router)
app.include_router(webhooks.router)


@app.on_event("startup")
async def startup_event():
    """Run web server startup tasks."""
    logger.info("Starting FastAPI web server...")
    logger.info("API Documentation available at: http://localhost:8000/docs")
    logger.info("ReDoc Documentation available at: http://localhost:8000/redoc")
    logger.info("OpenAPI Schema available at: http://localhost:8000/openapi.json")
    logger.info("OpenAPI Export available at: http://localhost:8000/openapi/export")
    # Background services (job runners, bot, etc.) are handled by worker.py
    logger.info("Web server startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Run web server shutdown tasks."""
    logger.info("Shutting down FastAPI web server...")
    # Only handle web server specific cleanup
    # Background services shutdown is handled by worker.py
    logger.info("Web server shutdown complete")
