"""Airdrop processing utilities for simple workflows.

This module provides functions to retrieve airdrop data from the database and format
it for consumption by LLMs during proposal evaluation.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from app.backend.factory import backend
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


async def fetch_airdrop(airdrop_id: UUID) -> Optional[Dict[str, Any]]:
    """Fetch stored airdrop data from database.

    Args:
        airdrop_id: Database ID of the airdrop record

    Returns:
        Dictionary containing airdrop data or None if failed
    """
    try:
        airdrop = backend.get_airdrop(airdrop_id)
        if not airdrop:
            logger.warning(f"Airdrop with ID {airdrop_id} not found in database")
            return None

        # Convert to dictionary format
        airdrop_data = {
            "id": str(airdrop.id),
            "tx_hash": airdrop.tx_hash,
            "block_height": airdrop.block_height,
            "timestamp": airdrop.timestamp,
            "sender": airdrop.sender,
            "contract_identifier": airdrop.contract_identifier,
            "token_identifier": airdrop.token_identifier,
            "success": airdrop.success,
            "total_amount_airdropped": airdrop.total_amount_airdropped,
            "recipients": airdrop.recipients or [],
            "proposal_id": airdrop.proposal_id,
            "created_at": airdrop.created_at,
            "updated_at": airdrop.updated_at,
        }

        logger.debug(f"Retrieved airdrop data for ID {airdrop_id}")
        return airdrop_data

    except Exception as e:
        logger.error(f"Error retrieving airdrop data for ID {airdrop_id}: {str(e)}")
        return None


def format_airdrop(airdrop_data: Dict[str, Any]) -> str:
    """Format airdrop data for inclusion in proposal evaluation content.

    Args:
        airdrop_data: Airdrop data dictionary from database

    Returns:
        Formatted airdrop content for LLM analysis
    """
    try:
        tx_hash = airdrop_data.get("tx_hash", "")
        block_height = airdrop_data.get("block_height", "")
        timestamp = airdrop_data.get("timestamp", "")
        sender = airdrop_data.get("sender", "")
        contract_identifier = airdrop_data.get("contract_identifier", "")
        token_identifier = airdrop_data.get("token_identifier", "")
        success = airdrop_data.get("success", False)
        total_amount = airdrop_data.get("total_amount_airdropped", "0")
        recipients = airdrop_data.get("recipients", [])
        proposal_id = airdrop_data.get("proposal_id", "")

        # Format timestamp
        timestamp_str = ""
        if timestamp:
            try:
                if hasattr(timestamp, "strftime"):
                    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                else:
                    timestamp_str = str(timestamp)
            except (AttributeError, ValueError, TypeError):
                timestamp_str = str(timestamp)

        # Format recipients list (show count and sample)
        recipients_count = len(recipients)
        recipients_sample = ""
        if recipients:
            # Show first few recipients as examples
            sample_size = min(3, len(recipients))
            recipients_sample = ", ".join(recipients[:sample_size])
            if len(recipients) > sample_size:
                recipients_sample += f", ... and {len(recipients) - sample_size} more"

        # Extract token name from identifier if possible
        token_name = token_identifier
        if "::" in token_identifier:
            token_name = token_identifier.split("::")[-1]

        formatted_airdrop = f"""
<airdrop>
  <transaction_hash>{tx_hash}</transaction_hash>
  <block_height>{block_height}</block_height>
  <timestamp>{timestamp_str}</timestamp>
  <sender>{sender}</sender>
  <contract_identifier>{contract_identifier}</contract_identifier>
  <token_identifier>{token_identifier}</token_identifier>
  <token_name>{token_name}</token_name>
  <success>{success}</success>
  <total_amount_distributed>{total_amount}</total_amount_distributed>
  <recipients_count>{recipients_count}</recipients_count>
  <recipients_sample>{recipients_sample or "None"}</recipients_sample>
  <linked_proposal_id>{proposal_id or "None"}</linked_proposal_id>
</airdrop>
"""
        return formatted_airdrop.strip()

    except Exception as e:
        logger.error(f"Error formatting airdrop content: {str(e)}")
        return f"<airdrop><error>Error formatting airdrop: {str(e)}</error></airdrop>"


async def process_airdrop(
    airdrop_id: UUID,
    proposal_id: str = "unknown",
) -> Optional[str]:
    """Process airdrop database ID to retrieve and format airdrop data.

    Args:
        airdrop_id: Airdrop database ID to process
        proposal_id: Optional proposal ID for logging

    Returns:
        Formatted airdrop content or None if failed
    """
    if not airdrop_id:
        logger.info(
            f"[AirdropProcessor:{proposal_id}] No airdrop_id provided, skipping."
        )
        return None

    logger.info(f"[AirdropProcessor:{proposal_id}] Processing airdrop ID: {airdrop_id}")

    try:
        # Get stored airdrop content
        airdrop_data = await fetch_airdrop(airdrop_id)
        if not airdrop_data:
            logger.warning(
                f"[AirdropProcessor:{proposal_id}] Could not retrieve airdrop: {airdrop_id}"
            )
            return None

        # Format airdrop content
        formatted_airdrop = format_airdrop(airdrop_data)

        logger.info(
            f"[AirdropProcessor:{proposal_id}] Successfully processed airdrop {airdrop_id}"
        )
        logger.debug(
            f"[AirdropProcessor:{proposal_id}] Formatted airdrop content: {formatted_airdrop[:200]}..."
        )

        return formatted_airdrop

    except Exception as e:
        logger.error(
            f"[AirdropProcessor:{proposal_id}] Error processing airdrop {airdrop_id}: {str(e)}"
        )
        return None


def get_airdrop_summary(airdrop_data: Dict[str, Any]) -> str:
    """Get a brief summary of airdrop data for logging.

    Args:
        airdrop_data: Airdrop data dictionary

    Returns:
        Brief summary string
    """
    try:
        token_name = airdrop_data.get("token_identifier", "Unknown")
        if "::" in token_name:
            token_name = token_name.split("::")[-1]

        amount = airdrop_data.get("total_amount_airdropped", "0")
        recipients_count = len(airdrop_data.get("recipients", []))
        success = airdrop_data.get("success", False)

        return f"{token_name} airdrop: {amount} tokens to {recipients_count} recipients ({'successful' if success else 'failed'})"
    except Exception as e:
        return f"Airdrop summary error: {str(e)}"
