import os
from backend.factory import backend
from backend.models import (
    ContractStatus,
    ExtensionBase,
    ExtensionFilter,
    ProposalBase,
    ProposalFilter,
    TokenBase,
    TokenFilter,
)
from dataclasses import dataclass
from fastapi import APIRouter, Body, HTTPException
from lib.logger import configure_logger
from pydantic import BaseModel
from typing import List

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/webhooks")

# Create webhooks directory if it doesn't exist
WEBHOOKS_DIR = "webhooks"
os.makedirs(WEBHOOKS_DIR, exist_ok=True)


class TestMessageResponse(BaseModel):
    """Response model for test message endpoint."""

    success: bool
    message: str


@dataclass
class TransactionIdentifier:
    hash: str


@dataclass
class TransactionWithReceipt:
    transaction_identifier: TransactionIdentifier


@dataclass
class Apply:
    transactions: List[TransactionWithReceipt]


@dataclass
class WebhookData:
    apply: List[Apply]


@router.post("/chainhook")
async def chainhook(
    data: WebhookData = Body(...),
) -> TestMessageResponse:
    """Handle a chainhook webhook.

    Args:
        data (WebhookData): The webhook payload as JSON

    Returns:
        TestMessageResponse: A JSON response with the result of the operation

    Raises:
        HTTPException: If the webhook cannot be processed
    """
    try:
        logger.debug(f"Received chainhook webhook: {data}")
        non_processed_extensions = backend.list_extensions(
            filters=ExtensionFilter(
                status=ContractStatus.DRAFT,
            )
        )
        non_processed_tokens = backend.list_tokens(
            filters=TokenFilter(
                status=ContractStatus.DRAFT,
            )
        )
        non_processed_proposals = backend.list_proposals(
            filters=ProposalFilter(
                status=ContractStatus.DRAFT,
            )
        )
        for apply in data.apply:
            for transaction in apply.transactions:
                tx_id = transaction.transaction_identifier.hash
                for extension in non_processed_extensions:
                    if extension.tx_id == tx_id:
                        extension.status = ContractStatus.DEPLOYED
                        backend.update_extension(
                            extension.id,
                            update_data=ExtensionBase(status=ContractStatus.DEPLOYED),
                        )
                for token in non_processed_tokens:
                    if token.tx_id == tx_id:
                        token.status = ContractStatus.DEPLOYED
                        backend.update_token(
                            token.id,
                            update_data=TokenBase(status=ContractStatus.DEPLOYED),
                        )
                for proposal in non_processed_proposals:
                    if proposal.tx_id == tx_id:
                        proposal.status = ContractStatus.DEPLOYED
                        backend.update_proposal(
                            proposal.id,
                            update_data=ProposalBase(status=ContractStatus.DEPLOYED),
                        )
        return TestMessageResponse(
            success=True,
            message=f"Successfully processed webhook",
        )
    except Exception as e:
        logger.error(f"Error handling chainhook webhook: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing webhook",
        )
