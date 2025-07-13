from typing import Any, Dict
import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.dependencies import verify_webhook_auth
from app.lib.logger import configure_logger
from app.services.integrations.webhooks.base import WebhookResponse
from app.services.integrations.webhooks.chainhook import ChainhookService
from app.services.integrations.webhooks.dao import DAOService

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/webhooks")


# Pydantic models for request/response documentation
class ChainhookEventData(BaseModel):
    """Model for chainhook webhook event data."""

    event_type: str = Field(
        ..., description="Type of blockchain event", example="block_confirmed"
    )
    block_height: int = Field(
        ..., description="Block height where event occurred", example=12345
    )
    transaction_id: str = Field(..., description="Transaction ID", example="0x1234...")
    contract_address: str = Field(
        ..., description="Smart contract address", example="SP..."
    )
    event_data: Dict[str, Any] = Field(..., description="Event-specific data payload")


class DAOCreationData(BaseModel):
    """Model for DAO creation webhook data."""

    dao_name: str = Field(..., description="Name of the created DAO", example="MyDAO")
    dao_contract: str = Field(..., description="DAO contract address", example="SP...")
    token_contract: str = Field(
        ..., description="Token contract address", example="SP..."
    )
    extensions: list = Field(
        ..., description="List of DAO extensions", example=["voting", "treasury"]
    )


class WebhookErrorResponse(BaseModel):
    """Model for webhook error responses."""

    detail: str = Field(
        ..., description="Error message", example="Invalid authentication token"
    )


async def process_chainhook_async(data: Dict[str, Any]) -> None:
    """Process chainhook webhook asynchronously with logging.

    Args:
        data: The webhook payload as JSON
    """
    service = ChainhookService()

    try:
        logger.info("Starting async chainhook processing")
        result = await service.process(data)
        logger.info(f"Chainhook processing completed successfully: {result}")
    except Exception as e:
        logger.error(f"Chainhook processing failed: {str(e)}", exc_info=True)


@router.post(
    "/chainhook",
    status_code=204,
    summary="Process Chainhook Events",
    description="Handle blockchain events from chainhook services for asynchronous processing",
    responses={
        204: {
            "description": "Event accepted for processing (asynchronous)",
        },
        401: {
            "description": "Authentication failed",
            "model": WebhookErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid authentication token"}
                }
            },
        },
        500: {"description": "Internal server error", "model": WebhookErrorResponse},
    },
    tags=["webhooks"],
    security=[{"BearerAuth": []}],
)
async def chainhook(
    data: Dict[str, Any] = Body(
        ...,
        description="Chainhook event payload from blockchain monitoring service",
        example={
            "event_type": "block_confirmed",
            "block_height": 12345,
            "transaction_id": "0x1234567890abcdef",
            "contract_address": "SP1234567890ABCDEF.contract-name",
            "event_data": {
                "function_name": "transfer",
                "parameters": {"from": "SP...", "to": "SP...", "amount": "1000"},
            },
        },
    ),
    _: None = Depends(verify_webhook_auth),
) -> Response:
    """
    Handle blockchain events from chainhook services.

    This endpoint receives blockchain events from chainhook monitoring services
    and processes them asynchronously. The endpoint returns immediately with a
    204 status code while processing continues in the background.

    **Authentication:** Requires Bearer token authentication via Authorization header.
    The token must match the one configured in `AIBTC_WEBHOOK_AUTH_TOKEN`.

    **Processing:**
    - Events are processed asynchronously to ensure fast response times
    - Failed processing is logged but does not affect the HTTP response
    - Supports various blockchain event types (transactions, blocks, contract calls)

    **Event Types Supported:**
    - Block confirmations
    - Transaction events
    - Smart contract interactions
    - DAO-related activities

    **Security:** Only authorized chainhook services should call this endpoint.
    """
    # Start async processing without awaiting
    asyncio.create_task(process_chainhook_async(data))

    # Return 204 immediately
    return Response(status_code=204)


@router.post(
    "/dao",
    response_model=WebhookResponse,
    summary="Handle DAO Creation Events",
    description="Process DAO creation webhooks and setup associated entities",
    responses={
        200: {
            "description": "DAO creation processed successfully",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "DAO created successfully",
                        "data": {
                            "dao_id": "12345678-1234-1234-1234-123456789abc",
                            "dao_name": "MyDAO",
                            "contract_address": "SP1234567890ABCDEF.my-dao",
                            "token_address": "SP1234567890ABCDEF.my-dao-token",
                            "extensions_created": 3,
                        },
                    }
                }
            },
        },
        401: {"description": "Authentication failed", "model": WebhookErrorResponse},
        422: {
            "description": "Invalid webhook payload",
            "model": WebhookErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Missing required field: dao_name"}
                }
            },
        },
        500: {
            "description": "Internal server error during DAO creation",
            "model": WebhookErrorResponse,
        },
    },
    tags=["webhooks"],
    security=[{"BearerAuth": []}],
)
async def dao_creation(
    data: Dict[str, Any] = Body(
        ...,
        description="DAO creation webhook payload containing DAO, extensions, and token data",
        example={
            "dao_name": "MyDAO",
            "dao_description": "A decentralized autonomous organization for community governance",
            "dao_contract": "SP1234567890ABCDEF.my-dao",
            "token_contract": "SP1234567890ABCDEF.my-dao-token",
            "token_name": "MyDAO Token",
            "token_symbol": "MYDAO",
            "extensions": [
                {"name": "voting", "contract": "SP1234567890ABCDEF.dao-voting"},
                {"name": "treasury", "contract": "SP1234567890ABCDEF.dao-treasury"},
            ],
            "created_by": "SP1234567890ABCDEF",
            "network": "testnet",
        },
    ),
    _: None = Depends(verify_webhook_auth),
) -> WebhookResponse:
    """
    Handle DAO creation events and setup associated entities.

    This endpoint processes webhook payloads for creating a new DAO along with
    its associated extensions and token. It creates database records and sets up
    the necessary infrastructure for the DAO to function.

    **Authentication:** Requires Bearer token authentication via Authorization header.
    The token must match the one configured in `AIBTC_WEBHOOK_AUTH_TOKEN`.

    **Processing:**
    - Creates DAO record in database
    - Sets up DAO extensions (voting, treasury, etc.)
    - Creates token record and metadata
    - Establishes relationships between entities
    - Returns detailed response with created entity information

    **DAO Components Created:**
    - Core DAO entity with governance parameters
    - Token contract for DAO membership/voting
    - Extensions for specific functionality (voting, treasury, proposals)
    - Initial configuration and permissions

    **Networks Supported:**
    - Testnet (for development and testing)
    - Mainnet (for production deployments)

    **Error Handling:**
    - Validates required fields in webhook payload
    - Handles duplicate DAO creation attempts
    - Provides detailed error messages for debugging
    """
    service = DAOService()

    try:
        logger.info("Processing DAO creation webhook")
        result = await service.process(data)
        return WebhookResponse(**result)
    except Exception as e:
        logger.error(f"Error processing DAO creation webhook: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error processing DAO creation webhook: {str(e)}"
        )
