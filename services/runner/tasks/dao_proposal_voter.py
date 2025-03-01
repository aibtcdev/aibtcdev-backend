"""DAO proposal voter task implementation."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import QueueMessage, QueueMessageFilter
from lib.logger import configure_logger
from services.runner.base import BaseTask
from services.workflows.proposal_evaluation import evaluate_and_vote_on_proposal

logger = configure_logger(__name__)


class DAOProposalVoterTask(BaseTask):
    """Task runner for processing and voting on DAO proposals."""

    QUEUE_TYPE = "dao_proposal_vote"
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7
    DEFAULT_AUTO_VOTE = True

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single DAO proposal voting message.

        Args:
            message: The queue message to process

        Returns:
            Dict[str, Any]: Result of processing the message
        """
        message_id = message.id
        message_data = message.message or {}
        wallet_id = message.wallet_id

        logger.info(f"Processing DAO proposal voting message: {message_id}")

        # Extract required parameters from the message
        action_proposals_contract = message_data.get("action_proposals_contract")
        proposal_id = message_data.get("proposal_id")
        dao_name = message_data.get("dao_name")

        if not action_proposals_contract or proposal_id is None:
            error_msg = f"Missing required parameters in message {message_id}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        try:
            # Convert proposal_id to int if it's a string
            if isinstance(proposal_id, str):
                proposal_id = int(proposal_id)

            # Execute the proposal evaluation workflow
            logger.info(
                f"Evaluating proposal {proposal_id} for contract "
                f"{action_proposals_contract}, DAO: {dao_name}"
            )

            result = await evaluate_and_vote_on_proposal(
                action_proposals_contract=action_proposals_contract,
                proposal_id=proposal_id,
                dao_name=dao_name,
                wallet_id=wallet_id,
                auto_vote=self.DEFAULT_AUTO_VOTE,
                confidence_threshold=self.DEFAULT_CONFIDENCE_THRESHOLD,
            )

            # Log the results
            evaluation = result.get("evaluation", {})
            approval = evaluation.get("approve", False)
            confidence = evaluation.get("confidence_score", 0.0)
            reasoning = evaluation.get("reasoning", "No reasoning provided")

            logger.info(
                f"Proposal {proposal_id} evaluation complete: "
                f"Approve: {approval}, Confidence: {confidence:.2f}"
            )
            logger.debug(f"Reasoning: {reasoning}")

            if result.get("auto_voted", False):
                logger.info(
                    f"Automatically voted {'FOR' if approval else 'AGAINST'} "
                    f"proposal {proposal_id} with confidence {confidence:.2f}"
                )
            else:
                logger.info(
                    f"Did not auto-vote on proposal {proposal_id} "
                    f"(confidence {confidence:.2f} < threshold)"
                )

            # Mark the message as processed
            backend.update_queue_message(message_id, {"is_processed": True})

            return {
                "success": True,
                "auto_voted": result.get("auto_voted", False),
                "approve": approval,
            }

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed messages from the queue.

        Returns:
            List[QueueMessage]: List of pending messages
        """
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def execute(self, context) -> List[Dict[str, Any]]:
        """Run the DAO proposal voter task.

        Args:
            context: The job context

        Returns:
            List[Dict[str, Any]]: Results of task execution
        """
        start_time = datetime.now()
        logger.info(f"Starting DAO proposal voter task at {start_time}")

        pending_messages = await self.get_pending_messages()
        logger.info(f"Found {len(pending_messages)} pending messages")

        if not pending_messages:
            return [
                {
                    "success": True,
                    "message": "No pending messages found",
                    "proposals_processed": 0,
                    "proposals_voted": 0,
                    "errors": [],
                }
            ]

        # Process each message
        processed_count = 0
        voted_count = 0
        errors = []

        for message in pending_messages:
            result = await self.process_message(message)
            processed_count += 1

            if result.get("success"):
                if result.get("auto_voted", False):
                    voted_count += 1
            else:
                errors.append(result.get("error", "Unknown error"))

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        logger.info(
            f"DAO proposal voter task completed in {execution_time:.2f}s. "
            f"Processed: {processed_count}, Voted: {voted_count}, Errors: {len(errors)}"
        )

        return [
            {
                "success": True,
                "message": f"Processed {processed_count} proposal(s), voted on {voted_count} proposal(s)",
                "proposals_processed": processed_count,
                "proposals_voted": voted_count,
                "errors": errors,
                "start_time": start_time,
                "end_time": end_time,
                "execution_time": execution_time,
            }
        ]


# Instantiate the task for use in the registry
dao_proposal_voter = DAOProposalVoterTask()
