"""Unit tests for the DAO proposal voter task."""

import datetime
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from backend.models import QueueMessage
from services.runner.base import JobContext, JobType
from services.runner.tasks.dao_proposal_voter import DAOProposalVoterTask


class TestDAOProposalVoterTask(unittest.TestCase):
    """Test cases for the DAO proposal voter task."""

    def setUp(self):
        """Set up the test case."""
        # Create a test task instance
        self.task = DAOProposalVoterTask()

        # Mock the configuration
        self.task.config = MagicMock()

        # Create a test job context
        self.context = JobContext(
            job_type=JobType.DAO_PROPOSAL_VOTE,
            config=self.task.config,
            parameters={},
        )

        # Mock queue messages
        self.test_queue_message = QueueMessage(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            created_at=datetime.datetime.now(),
            type="dao_proposal_vote",
            message={
                "action_proposals_contract": "SP123.dao-action-proposals",
                "proposal_id": 1,
                "dao_name": "TestDAO",
                "tx_id": "0x1234567890",
            },
            wallet_id=UUID("98765432-9876-5432-9876-543298765432"),
            is_processed=False,
        )

    @patch("services.runner.tasks.dao_proposal_voter.backend")
    @patch("services.runner.tasks.dao_proposal_voter.evaluate_and_vote_on_proposal")
    async def test_process_message_success(self, mock_evaluate, mock_backend):
        """Test processing a message successfully."""
        # Mock the evaluate_and_vote_on_proposal function
        mock_evaluate.return_value = {
            "success": True,
            "evaluation": {
                "approve": True,
                "confidence_score": 0.85,
                "reasoning": "This is a good proposal",
            },
            "auto_voted": True,
        }

        # Process the test message
        result = await self.task.process_message(self.test_queue_message)

        # Check that the result is correct
        self.assertTrue(result["success"])
        self.assertTrue(result["auto_voted"])
        self.assertTrue(result["approve"])

        # Check that evaluate_and_vote_on_proposal was called with the correct parameters
        mock_evaluate.assert_called_once_with(
            action_proposals_contract="SP123.dao-action-proposals",
            proposal_id=1,
            dao_name="TestDAO",
            wallet_id=UUID("98765432-9876-5432-9876-543298765432"),
            auto_vote=True,
            confidence_threshold=0.7,
        )

        # Check that the message was marked as processed
        mock_backend.update_queue_message.assert_called_once_with(
            UUID("12345678-1234-5678-1234-567812345678"),
            {"is_processed": True},
        )

    @patch("services.runner.tasks.dao_proposal_voter.backend")
    @patch("services.runner.tasks.dao_proposal_voter.evaluate_and_vote_on_proposal")
    async def test_process_message_missing_parameters(
        self, mock_evaluate, mock_backend
    ):
        """Test processing a message with missing parameters."""
        # Create a message with missing parameters
        message = QueueMessage(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            created_at=datetime.datetime.now(),
            type="dao_proposal_vote",
            message={
                # Missing action_proposals_contract
                "proposal_id": 1,
                "dao_name": "TestDAO",
            },
            wallet_id=UUID("98765432-9876-5432-9876-543298765432"),
            is_processed=False,
        )

        # Process the message
        result = await self.task.process_message(message)

        # Check that the result indicates failure
        self.assertFalse(result["success"])
        self.assertIn("Missing required parameters", result["error"])

        # Check that evaluate_and_vote_on_proposal was not called
        mock_evaluate.assert_not_called()

        # Check that the message was not marked as processed
        mock_backend.update_queue_message.assert_not_called()

    @patch("services.runner.tasks.dao_proposal_voter.backend")
    async def test_get_pending_messages(self, mock_backend):
        """Test retrieving pending messages."""
        # Mock the list_queue_messages function
        mock_backend.list_queue_messages.return_value = [self.test_queue_message]

        # Get pending messages
        messages = await self.task.get_pending_messages()

        # Check that the correct messages were returned
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].id, self.test_queue_message.id)

        # Check that list_queue_messages was called with the correct parameters
        mock_backend.list_queue_messages.assert_called_once()
        filters = mock_backend.list_queue_messages.call_args[1]["filters"]
        self.assertEqual(filters.type, "dao_proposal_vote")
        self.assertFalse(filters.is_processed)

    @patch(
        "services.runner.tasks.dao_proposal_voter.DAOProposalVoterTask.get_pending_messages"
    )
    @patch(
        "services.runner.tasks.dao_proposal_voter.DAOProposalVoterTask.process_message"
    )
    async def test_execute_no_messages(self, mock_process, mock_get_messages):
        """Test executing the task when there are no messages."""
        # Mock get_pending_messages to return an empty list
        mock_get_messages.return_value = []

        # Execute the task
        results = await self.task.execute(self.context)

        # Check that results are correct
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])
        self.assertEqual(results[0]["proposals_processed"], 0)
        self.assertEqual(results[0]["proposals_voted"], 0)
        self.assertEqual(len(results[0]["errors"]), 0)

        # Check that process_message was not called
        mock_process.assert_not_called()

    @patch(
        "services.runner.tasks.dao_proposal_voter.DAOProposalVoterTask.get_pending_messages"
    )
    @patch(
        "services.runner.tasks.dao_proposal_voter.DAOProposalVoterTask.process_message"
    )
    async def test_execute_with_messages(self, mock_process, mock_get_messages):
        """Test executing the task with pending messages."""
        # Mock get_pending_messages to return test messages
        mock_get_messages.return_value = [
            self.test_queue_message,
            self.test_queue_message,
        ]

        # Mock process_message to return success for the first message and failure for the second
        mock_process.side_effect = [
            {"success": True, "auto_voted": True, "approve": True},
            {"success": False, "error": "Test error"},
        ]

        # Execute the task
        results = await self.task.execute(self.context)

        # Check that results are correct
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])
        self.assertEqual(results[0]["proposals_processed"], 2)
        self.assertEqual(results[0]["proposals_voted"], 1)
        self.assertEqual(len(results[0]["errors"]), 1)
        self.assertEqual(results[0]["errors"][0], "Test error")

        # Check that process_message was called twice
        self.assertEqual(mock_process.call_count, 2)
        mock_process.assert_any_call(self.test_queue_message)


if __name__ == "__main__":
    unittest.main()
