"""Tests for the SellEventHandler."""

import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from backend.models import WalletTokenBase
from services.webhooks.chainhook.handlers.sell_event_handler import SellEventHandler
from services.webhooks.chainhook.models import (
    Event,
    Receipt,
    TransactionIdentifier,
    TransactionMetadata,
    TransactionWithReceipt,
)


class TestSellEventHandler(unittest.TestCase):
    """Test cases for SellEventHandler."""

    def setUp(self):
        """Set up the test environment."""
        self.handler = SellEventHandler()

        # Create a mock logger
        self.handler.logger = MagicMock()

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

        # Create sample transaction metadata
        self.sample_metadata = TransactionMetadata(
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
        )

        # Create a sample transaction
        self.sample_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=self.sample_metadata,
            operations=[],
        )

    def test_can_handle_sell_transaction(self):
        """Test that the handler can handle sell transactions."""
        # Test with a sell transaction
        result = self.handler.can_handle(self.sample_transaction)
        self.assertTrue(result)

        # Test with a sell-tokens transaction
        sell_tokens_metadata = TransactionMetadata(
            description="Test sell-tokens transaction",
            execution_cost={"read_count": 10, "write_count": 5, "runtime": 100},
            fee=1000,
            kind={
                "type": "ContractCall",
                "data": {
                    "method": "sell-tokens",
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

        sell_tokens_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=sell_tokens_metadata,
            operations=[],
        )

        result = self.handler.can_handle(sell_tokens_transaction)
        self.assertTrue(result)

    def test_cannot_handle_non_sell_transaction(self):
        """Test that the handler cannot handle non-sell transactions."""
        # Create a non-sell transaction
        non_sell_metadata = TransactionMetadata(
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
        )

        non_sell_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=non_sell_metadata,
            operations=[],
        )

        result = self.handler.can_handle(non_sell_transaction)
        self.assertFalse(result)

    @patch("backend.factory.backend")
    @patch("services.webhooks.chainhook.handlers.sell_event_handler.configure_logger")
    async def test_handle_transaction_with_wallet_token(
        self, mock_configure_logger, mock_backend
    ):
        """Test that the handler correctly updates token balances when selling tokens."""
        # Set up the mock logger
        mock_logger = MagicMock()
        mock_configure_logger.return_value = mock_logger

        # Create a new handler with the mocked logger
        handler = SellEventHandler()

        # Mock the wallet and token data
        mock_wallet = MagicMock()
        mock_wallet.id = UUID("00000000-0000-0000-0000-000000000001")
        mock_token = MagicMock()
        mock_token.id = UUID("00000000-0000-0000-0000-000000000002")
        mock_token.dao_id = UUID("00000000-0000-0000-0000-000000000003")

        # Mock the wallet token record
        mock_wallet_token = MagicMock()
        mock_wallet_token.id = UUID("00000000-0000-0000-0000-000000000004")
        mock_wallet_token.wallet_id = mock_wallet.id
        mock_wallet_token.token_id = mock_token.id
        mock_wallet_token.dao_id = mock_token.dao_id
        mock_wallet_token.amount = "5000"  # Current amount before selling

        # Set up the mock backend responses
        mock_backend.list_wallets.return_value = [mock_wallet]
        mock_backend.list_tokens.return_value = [mock_token]
        mock_backend.list_wallet_tokens.return_value = [mock_wallet_token]

        # Handle the transaction
        await handler.handle_transaction(self.sample_transaction)

        # Check that the backend methods were called correctly
        mock_backend.list_wallets.assert_called_once()
        mock_backend.list_tokens.assert_called_once()
        mock_backend.list_wallet_tokens.assert_called_once()

        # Check that update_wallet_token was called with the correct parameters
        mock_backend.update_wallet_token.assert_called_once()
        call_args = mock_backend.update_wallet_token.call_args
        self.assertEqual(call_args[0][0], mock_wallet_token.id)

        # Check that the amount was decreased correctly (5000 - 1000 = 4000)
        update_data = call_args[0][1]
        self.assertIsInstance(update_data, WalletTokenBase)
        self.assertEqual(update_data.amount, "4000.0")
        self.assertEqual(update_data.wallet_id, mock_wallet.id)
        self.assertEqual(update_data.token_id, mock_token.id)
        self.assertEqual(update_data.dao_id, mock_token.dao_id)

    @patch("backend.factory.backend")
    @patch("services.webhooks.chainhook.handlers.sell_event_handler.configure_logger")
    async def test_handle_transaction_with_insufficient_balance(
        self, mock_configure_logger, mock_backend
    ):
        """Test that the handler correctly handles selling more tokens than available."""
        # Set up the mock logger
        mock_logger = MagicMock()
        mock_configure_logger.return_value = mock_logger

        # Create a new handler with the mocked logger
        handler = SellEventHandler()

        # Create an event with a large amount to sell (more than available)
        large_amount_event = Event(
            data={
                "asset_identifier": "ST123.test-token::TEST",
                "amount": "10000",  # More than the 5000 available
                "sender": "ST456",
                "recipient": "ST789",
            },
            position={"index": 0},
            type="FTTransferEvent",
        )

        # Update the receipt with the new event
        large_amount_receipt = Receipt(
            contract_calls_stack=[],
            events=[large_amount_event],
            mutated_assets_radius=[],
            mutated_contracts_radius=[],
        )

        # Update the metadata with the new receipt
        large_amount_metadata = self.sample_metadata
        large_amount_metadata.receipt = large_amount_receipt

        # Create a new transaction with the updated metadata
        large_amount_transaction = TransactionWithReceipt(
            transaction_identifier=TransactionIdentifier(hash="0xabcdef1234567890"),
            metadata=large_amount_metadata,
            operations=[],
        )

        # Mock the wallet and token data
        mock_wallet = MagicMock()
        mock_wallet.id = UUID("00000000-0000-0000-0000-000000000001")
        mock_token = MagicMock()
        mock_token.id = UUID("00000000-0000-0000-0000-000000000002")
        mock_token.dao_id = UUID("00000000-0000-0000-0000-000000000003")

        # Mock the wallet token record with a smaller amount than being sold
        mock_wallet_token = MagicMock()
        mock_wallet_token.id = UUID("00000000-0000-0000-0000-000000000004")
        mock_wallet_token.wallet_id = mock_wallet.id
        mock_wallet_token.token_id = mock_token.id
        mock_wallet_token.dao_id = mock_token.dao_id
        mock_wallet_token.amount = "5000"  # Less than the 10000 being sold

        # Set up the mock backend responses
        mock_backend.list_wallets.return_value = [mock_wallet]
        mock_backend.list_tokens.return_value = [mock_token]
        mock_backend.list_wallet_tokens.return_value = [mock_wallet_token]

        # Handle the transaction
        await handler.handle_transaction(large_amount_transaction)

        # Check that update_wallet_token was called with the correct parameters
        mock_backend.update_wallet_token.assert_called_once()
        call_args = mock_backend.update_wallet_token.call_args

        # Check that the amount was set to 0 (not negative)
        update_data = call_args[0][1]
        self.assertEqual(update_data.amount, "0.0")


if __name__ == "__main__":
    unittest.main()
