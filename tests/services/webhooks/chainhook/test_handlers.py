"""Tests for the chainhook handlers."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.webhooks.chainhook.handlers import (
    ContractMessageHandler,
    TransactionStatusHandler,
)
from services.webhooks.chainhook.models import (
    TransactionIdentifier,
    TransactionWithReceipt,
)


class TestContractMessageHandler(unittest.TestCase):
    """Tests for the ContractMessageHandler."""

    def setUp(self):
        """Set up the test environment."""
        self.handler = ContractMessageHandler()

        # Sample transaction that should be handled
        self.message_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata={
                "kind": {
                    "type": "ContractCall",
                    "data": {
                        "method": "send",
                        "args": ["test message"],
                        "contract_identifier": "ST1234567890ABCDEF.test-contract",
                    },
                },
                "success": False,
                "sender": "ST1234567890ABCDEF",
            },
            operations=[],
        )

        # Sample transaction that should not be handled
        self.non_message_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata={
                "kind": {
                    "type": "ContractCall",
                    "data": {
                        "method": "transfer",
                        "args": ["100", "ST1234567890ABCDEF"],
                        "contract_identifier": "ST1234567890ABCDEF.test-contract",
                    },
                },
                "success": True,
                "sender": "ST1234567890ABCDEF",
            },
            operations=[],
        )

    def test_can_handle(self):
        """Test the can_handle method."""
        # Should handle message transactions
        self.assertTrue(self.handler.can_handle(self.message_transaction))

        # Should not handle non-message transactions
        self.assertFalse(self.handler.can_handle(self.non_message_transaction))

    @patch("backend.factory.backend")
    async def test_handle_transaction(self, mock_backend):
        """Test the handle_transaction method."""
        # Mock the backend methods
        mock_extension = MagicMock()
        mock_extension.dao_id = "test-dao-id"
        mock_backend.list_extensions.return_value = [mock_extension]
        mock_backend.create_queue_message.return_value = {"id": "test-message-id"}

        # Call the handler
        await self.handler.handle_transaction(self.message_transaction)

        # Verify the backend methods were called correctly
        mock_backend.list_extensions.assert_called_once()
        mock_backend.create_queue_message.assert_called_once()

        # Check that the message was created with the correct parameters
        call_args = mock_backend.create_queue_message.call_args[0][0]
        self.assertEqual(call_args.type, "tweet")
        self.assertEqual(call_args.message, {"message": "test message"})
        self.assertEqual(call_args.dao_id, "test-dao-id")


class TestTransactionStatusHandler(unittest.TestCase):
    """Tests for the TransactionStatusHandler."""

    def setUp(self):
        """Set up the test environment."""
        self.handler = TransactionStatusHandler()

        # Sample transaction
        self.transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata={
                "kind": {
                    "type": "ContractCall",
                    "data": {
                        "method": "deploy",
                        "contract_identifier": "ST1234567890ABCDEF.test-contract",
                    },
                },
                "success": True,
                "sender": "ST1234567890ABCDEF",
            },
            operations=[],
        )

    def test_can_handle(self):
        """Test the can_handle method."""
        # Should handle any transaction
        self.assertTrue(self.handler.can_handle(self.transaction))

    @patch("backend.factory.backend")
    async def test_handle_transaction(self, mock_backend):
        """Test the handle_transaction method."""
        # Mock the backend methods
        mock_extension = MagicMock()
        mock_extension.id = "test-extension-id"
        mock_extension.status = "PENDING"
        mock_extension.tx_id = "0xabcdef1234567890"

        mock_token = MagicMock()
        mock_token.id = "test-token-id"
        mock_token.status = "PENDING"
        mock_token.tx_id = "0xabcdef1234567890"

        mock_proposal = MagicMock()
        mock_proposal.id = "test-proposal-id"
        mock_proposal.status = "PENDING"
        mock_proposal.tx_id = "other-tx-id"

        mock_backend.list_extensions.return_value = [mock_extension]
        mock_backend.list_tokens.return_value = [mock_token]
        mock_backend.list_proposals.return_value = [mock_proposal]

        # Call the handler
        await self.handler.handle_transaction(self.transaction)

        # Verify the backend methods were called correctly
        mock_backend.list_extensions.assert_called_once()
        mock_backend.list_tokens.assert_called_once()
        mock_backend.list_proposals.assert_called_once()

        # Check that the extension and token were updated but not the proposal
        mock_backend.update_extension.assert_called_once()
        mock_backend.update_token.assert_called_once()
        mock_backend.update_proposal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
