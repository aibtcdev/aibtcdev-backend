"""Tests for the BuyEventHandler."""

import unittest
from unittest.mock import MagicMock, patch

from services.webhooks.chainhook.handlers.buy_event_handler import BuyEventHandler
from services.webhooks.chainhook.models import (
    Event,
    Receipt,
    TransactionIdentifier,
    TransactionMetadata,
    TransactionWithReceipt,
)


class TestBuyEventHandler(unittest.TestCase):
    """Test cases for BuyEventHandler."""

    def setUp(self):
        """Set up the test environment."""
        self.handler = BuyEventHandler()

        # Create a mock logger
        self.handler.logger = MagicMock()

        # Create a sample event
        self.sample_event = Event(
            data={"amount": "1000", "recipient": "ST123", "sender": "ST456"},
            position={"index": 0},
            type="STXTransferEvent",
        )

        # Create a sample receipt with events
        self.sample_receipt = Receipt(
            contract_calls_stack=[],
            events=[self.sample_event],
            mutated_assets_radius=[],
            mutated_contracts_radius=[],
        )

        # Create sample transaction metadata
        self.sample_metadata = TransactionMetadata(
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
        )

        # Create a sample transaction
        self.sample_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=self.sample_metadata,
            operations=[],
        )

    def test_can_handle_buy_transaction(self):
        """Test that the handler can handle buy transactions."""
        # Test with a buy transaction
        result = self.handler.can_handle(self.sample_transaction)
        self.assertTrue(result)

        # Test with a buy-tokens transaction
        buy_tokens_metadata = TransactionMetadata(
            description="Test buy-tokens transaction",
            execution_cost={"read_count": 10, "write_count": 5, "runtime": 100},
            fee=1000,
            kind={
                "type": "ContractCall",
                "data": {
                    "method": "buy-tokens",
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
        )

        buy_tokens_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=buy_tokens_metadata,
            operations=[],
        )

        result = self.handler.can_handle(buy_tokens_transaction)
        self.assertTrue(result)

    def test_cannot_handle_non_buy_transaction(self):
        """Test that the handler cannot handle non-buy transactions."""
        # Create a non-buy transaction
        non_buy_metadata = TransactionMetadata(
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
        )

        non_buy_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=non_buy_metadata,
            operations=[],
        )

        result = self.handler.can_handle(non_buy_transaction)
        self.assertFalse(result)

    @patch("services.webhooks.chainhook.handlers.buy_event_handler.configure_logger")
    async def test_handle_transaction(self, mock_configure_logger):
        """Test that the handler correctly logs events."""
        # Set up the mock logger
        mock_logger = MagicMock()
        mock_configure_logger.return_value = mock_logger

        # Create a new handler with the mocked logger
        handler = BuyEventHandler()

        # Handle the transaction
        await handler.handle_transaction(self.sample_transaction)

        # Check that the logger was called with the expected messages
        mock_logger.info.assert_any_call(
            "Processing buy function call from ST456 to contract ST123.test-contract "
            "with args: ['10'], tx_id: 0xabcdef1234567890"
        )

        mock_logger.info.assert_any_call(
            "Found 1 events in transaction 0xabcdef1234567890"
        )

        mock_logger.info.assert_any_call(
            "Event 1/1: Type=STXTransferEvent, Data={'amount': '1000', 'recipient': 'ST123', 'sender': 'ST456'}"
        )


if __name__ == "__main__":
    unittest.main()
