from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from app.api.dependencies import verify_webhook_auth
from app.lib.logger import configure_logger
from app.services.integrations.webhooks.base import WebhookResponse
from app.services.integrations.webhooks.chainhook import ChainhookService
from app.services.integrations.webhooks.dao import DAOService

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/webhooks")


@router.post("/chainhook")
async def chainhook(
    data: Dict[str, Any] = Body(...),
    _: None = Depends(verify_webhook_auth),
) -> Response:
    """Handle a chainhook webhook.

    This endpoint requires Bearer token authentication via the Authorization header.
    The token must match the one configured in AIBTC_WEBHOOK_AUTH_TOKEN.

    Always returns 200 status code regardless of processing outcome.

    Args:
        data: The webhook payload as JSON

    Returns:
        Response: 200 OK status always

    Raises:
        HTTPException: If authentication fails
    """
    service = ChainhookService()

    try:
        logger.debug(
            "Chainhook webhook received", extra={"event_type": "chainhook_webhook"}
        )
        await service.process(data)
        logger.info("Chainhook processing completed")
    except Exception as e:
        logger.error(
            "Chainhook processing failed", extra={"error": str(e)}, exc_info=True
        )

    return Response(status_code=200)


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
        logger.debug(
            "DAO creation webhook received",
            extra={"event_type": "dao_creation_webhook"},
        )
        result = await service.process(data)
        logger.info("DAO creation processing completed")
        return WebhookResponse(**result)
    except Exception as e:
        logger.error(
            "DAO creation processing failed", extra={"error": str(e)}, exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Error processing DAO creation webhook: {str(e)}"
        )
