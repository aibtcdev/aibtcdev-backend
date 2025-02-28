"""Webhook API endpoints."""

import os
from fastapi import APIRouter, Body, HTTPException
from lib.logger import configure_logger
from services.webhooks.base import WebhookResponse
from services.webhooks.chainhook import ChainhookService
from services.webhooks.github import GitHubService
from typing import Any, Dict

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/webhooks")


@router.post("/chainhook")
async def chainhook(
    data: Dict[str, Any] = Body(...),
) -> WebhookResponse:
    """Handle a chainhook webhook.

    Args:
        data: The webhook payload as JSON

    Returns:
        WebhookResponse: A JSON response with the result of the operation

    Raises:
        HTTPException: If the webhook cannot be processed
    """
    service = ChainhookService()

    try:
        result = await service.process(data)
        return WebhookResponse(**result)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing webhook")


@router.post("/github")
async def github_webhook(
    data: Dict[str, Any] = Body(...),
) -> WebhookResponse:
    """Handle a GitHub webhook.

    Args:
        data: The webhook payload as JSON

    Returns:
        WebhookResponse: A JSON response with the result of the operation

    Raises:
        HTTPException: If the webhook cannot be processed
    """
    service = GitHubService()

    try:
        result = await service.process(data)
        return WebhookResponse(**result)
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing GitHub webhook")
