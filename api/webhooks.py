from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from api.dependencies import verify_webhook_auth
from lib.logger import configure_logger
from services.integrations.webhooks.base import WebhookResponse
from services.integrations.webhooks.chainhook import ChainhookService
from services.integrations.webhooks.dao import DAOService

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/webhooks")


@router.post("/chainhook")
async def chainhook(
    data: Dict[str, Any] = Body(...),
    _: None = Depends(verify_webhook_auth),
) -> WebhookResponse:
    """Handle a chainhook webhook.

    This endpoint requires Bearer token authentication via the Authorization header.
    The token must match the one configured in AIBTC_WEBHOOK_AUTH_TOKEN.

    Args:
        data: The webhook payload as JSON

    Returns:
        WebhookResponse: A JSON response with the result of the operation

    Raises:
        HTTPException: If authentication fails or the webhook cannot be processed
    """
    service = ChainhookService()

    try:
        result = await service.process(data)
        return WebhookResponse(**result)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing webhook")


@router.post("/dao")
async def dao_creation(
    data: Dict[str, Any] = Body(...),
    _: None = Depends(verify_webhook_auth),
) -> WebhookResponse:
    """Handle a DAO creation webhook.

    This endpoint requires Bearer token authentication via the Authorization header.
    The token must match the one configured in AIBTC_WEBHOOK_AUTH_TOKEN.

    This endpoint processes webhook payloads for creating a new DAO
    along with its associated extensions and token.

    Args:
        data: The webhook payload as JSON containing DAO, extensions, and token data

    Returns:
        WebhookResponse: A JSON response with the result of the operation and created entities

    Raises:
        HTTPException: If authentication fails or the webhook cannot be processed
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
