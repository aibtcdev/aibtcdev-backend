"""Tests for the chainhook handlers."""

import unittest
from unittest.mock import MagicMock, patch

from services.webhooks.chainhook.handlers import (
    BuyEventHandler,
    ContractMessageHandler,
    SellEventHandler,
    TransactionStatusHandler,
)
from services.webhooks.chainhook.models import (
    Event,
    Receipt,
    TransactionIdentifier,
    TransactionMetadata,
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


class TestBuyEventHandler(unittest.TestCase):
    """Tests for the BuyEventHandler."""

    def setUp(self):
        """Set up the test environment."""
        self.handler = BuyEventHandler()

        # Create a sample FT transfer event
        self.ft_transfer_event = Event(
            data={
                "asset_identifier": "ST123.test-token::TEST",
                "amount": "1000",
                "sender": "ST789",
                "recipient": "ST456",
            },
            position={"index": 0},
            type="FTTransferEvent",
        )

        # Create a sample receipt with events
        self.sample_receipt = Receipt(
            contract_calls_stack=[],
            events=[self.ft_transfer_event],
            mutated_assets_radius=[],
            mutated_contracts_radius=[],
        )

        # Sample buy transaction
        self.buy_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=TransactionMetadata(
                description="Test buy transaction",
                execution_cost={"read_count": 10, "write_count": 5, "runtime": 100},
                fee=1000,
                kind={
                    "type": "ContractCall",
                    "data": {
                        "method": "buy",
                        "args": ["10"],
                        "contract_identifier": "ST123.test-contract",
                    },
                },
                nonce=42,
                position={"index": 0},
                raw_tx="0x0123456789abcdef",
                receipt=self.sample_receipt,
                result="(ok true)",
                sender="ST456",
                sponsor=None,
                success=True,
            ),
            operations=[],
        )

        # Sample non-buy transaction
        self.non_buy_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=TransactionMetadata(
                description="Test non-buy transaction",
                execution_cost={"read_count": 10, "write_count": 5, "runtime": 100},
                fee=1000,
                kind={
                    "type": "ContractCall",
                    "data": {
                        "method": "transfer",
                        "args": ["10"],
                        "contract_identifier": "ST123.test-contract",
                    },
                },
                nonce=42,
                position={"index": 0},
                raw_tx="0x0123456789abcdef",
                receipt=self.sample_receipt,
                result="(ok true)",
                sender="ST456",
                sponsor=None,
                success=True,
            ),
            operations=[],
        )

    def test_can_handle(self):
        """Test the can_handle method."""
        # Should handle buy transactions
        self.assertTrue(self.handler.can_handle(self.buy_transaction))

        # Should not handle non-buy transactions
        self.assertFalse(self.handler.can_handle(self.non_buy_transaction))


class TestSellEventHandler(unittest.TestCase):
    """Tests for the SellEventHandler."""

    def setUp(self):
        """Set up the test environment."""
        self.handler = SellEventHandler()

        # Create a sample FT transfer event
        self.ft_transfer_event = Event(
            data={
                "asset_identifier": "ST123.test-token::TEST",
                "amount": "1000",
                "sender": "ST456",
                "recipient": "ST789",
            },
            position={"index": 0},
            type="FTTransferEvent",
        )

        # Create a sample receipt with events
        self.sample_receipt = Receipt(
            contract_calls_stack=[],
            events=[self.ft_transfer_event],
            mutated_assets_radius=[],
            mutated_contracts_radius=[],
        )

        # Sample sell transaction
        self.sell_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=TransactionMetadata(
                description="Test sell transaction",
                execution_cost={"read_count": 10, "write_count": 5, "runtime": 100},
                fee=1000,
                kind={
                    "type": "ContractCall",
                    "data": {
                        "method": "sell",
                        "args": ["10"],
                        "contract_identifier": "ST123.test-contract",
                    },
                },
                nonce=42,
                position={"index": 0},
                raw_tx="0x0123456789abcdef",
                receipt=self.sample_receipt,
                result="(ok true)",
                sender="ST456",
                sponsor=None,
                success=True,
            ),
            operations=[],
        )

        # Sample non-sell transaction
        self.non_sell_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=TransactionMetadata(
                description="Test non-sell transaction",
                execution_cost={"read_count": 10, "write_count": 5, "runtime": 100},
                fee=1000,
                kind={
                    "type": "ContractCall",
                    "data": {
                        "method": "transfer",
                        "args": ["10"],
                        "contract_identifier": "ST123.test-contract",
                    },
                },
                nonce=42,
                position={"index": 0},
                raw_tx="0x0123456789abcdef",
                receipt=self.sample_receipt,
                result="(ok true)",
                sender="ST456",
                sponsor=None,
                success=True,
            ),
            operations=[],
        )

    def test_can_handle(self):
        """Test the can_handle method."""
        # Should handle sell transactions
        self.assertTrue(self.handler.can_handle(self.sell_transaction))

        # Should not handle non-sell transactions
        self.assertFalse(self.handler.can_handle(self.non_sell_transaction))


if __name__ == "__main__":
    unittest.main()
