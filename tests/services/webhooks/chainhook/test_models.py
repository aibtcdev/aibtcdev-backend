"""Tests for the chainhook models."""

import unittest
from typing import Any, Dict

from services.webhooks.chainhook.models import (
    Apply,
    BlockIdentifier,
    BlockMetadata,
    ChainHookData,
    ChainHookInfo,
    Event,
    Operation,
    Predicate,
    Receipt,
    TransactionIdentifier,
    TransactionMetadata,
    TransactionWithReceipt,
)
from services.webhooks.chainhook.parser import ChainhookParser


class TestChainHookModels(unittest.TestCase):
    """Test cases for ChainHook data models."""

    def setUp(self):
        """Set up the test environment."""
        # Initialize parser
        self.parser = ChainhookParser()

        # Sample data for testing
        self.sample_data: Dict[str, Any] = {
            "apply": [
                {
                    "block_identifier": {"hash": "0x1234567890abcdef", "index": 123456},
                    "parent_block_identifier": {
                        "hash": "0x0000000000000000",
                        "index": 123455,
                    },
                    "timestamp": 1640995200,
                    "metadata": {
                        "bitcoin_anchor_block_identifier": {
                            "hash": "0xbtc0000000000000",
                            "index": 700000,
                        },
                        "block_time": 1640995100,
                        "pox_cycle_index": 123,
                        "pox_cycle_length": 20,
                        "pox_cycle_position": 10,
                        "tenure_height": 12345,
                    },
                    "transactions": [
                        {
                            "transaction_identifier": {"hash": "0xabcdef1234567890"},
                            "metadata": {
                                "description": "Test transaction",
                                "execution_cost": {
                                    "read_count": 10,
                                    "write_count": 5,
                                    "runtime": 100,
                                },
                                "fee": 1000,
                                "kind": {
                                    "type": "ContractCall",
                                    "data": {
                                        "method": "transfer",
                                        "args": ["123456"],
                                        "contract_identifier": "ST1234567890ABCDEF.test-contract",
                                    },
                                },
                                "nonce": 42,
                                "position": {"index": 0},
                                "raw_tx": "0x0123456789abcdef",
                                "receipt": {
                                    "contract_calls_stack": [],
                                    "events": [
                                        {
                                            "data": {
                                                "amount": "123456",
                                                "asset_identifier": "ST1234567890ABCDEF.test-token::token",
                                                "sender": "ST1234567890ABCDEF",
                                                "recipient": "ST0987654321FEDCBA",
                                            },
                                            "position": {"index": 0},
                                            "type": "FTTransferEvent",
                                        }
                                    ],
                                    "mutated_assets_radius": [
                                        "ST1234567890ABCDEF.test-token::token"
                                    ],
                                    "mutated_contracts_radius": [
                                        "ST1234567890ABCDEF.test-contract"
                                    ],
                                },
                                "result": "(ok true)",
                                "sender": "ST1234567890ABCDEF",
                                "sponsor": None,
                                "success": True,
                            },
                            "operations": [
                                {
                                    "account": {"address": "ST1234567890ABCDEF"},
                                    "amount": {
                                        "currency": {"decimals": 6, "symbol": "TOKEN"},
                                        "value": 123456,
                                    },
                                    "operation_identifier": {"index": 0},
                                    "related_operations": [{"index": 1}],
                                    "status": "SUCCESS",
                                    "type": "DEBIT",
                                },
                                {
                                    "account": {"address": "ST0987654321FEDCBA"},
                                    "amount": {
                                        "currency": {"decimals": 6, "symbol": "TOKEN"},
                                        "value": 123456,
                                    },
                                    "operation_identifier": {"index": 1},
                                    "related_operations": [{"index": 0}],
                                    "status": "SUCCESS",
                                    "type": "CREDIT",
                                },
                            ],
                        }
                    ],
                }
            ],
            "chainhook": {
                "is_streaming_blocks": False,
                "predicate": {"scope": "block_height", "higher_than": 123450},
                "uuid": "test-uuid-12345",
            },
            "events": [],
            "rollback": [],
        }

    def test_block_identifier(self):
        """Test BlockIdentifier model."""
        block_id = BlockIdentifier(hash="0x1234", index=123)
        self.assertEqual(block_id.hash, "0x1234")
        self.assertEqual(block_id.index, 123)

    def test_transaction_identifier(self):
        """Test TransactionIdentifier model."""
        tx_id = TransactionIdentifier(hash="0xabcd")
        self.assertEqual(tx_id.hash, "0xabcd")

    def test_parse_chainhook_payload(self):
        """Test the parse_chainhook_payload method of ChainhookParser."""
        result = self.parser.parse_chainhook_payload(self.sample_data)

        # Verify the result is of the correct type
        self.assertIsInstance(result, ChainHookData)

        # Verify chainhook info
        self.assertIsInstance(result.chainhook, ChainHookInfo)
        self.assertFalse(result.chainhook.is_streaming_blocks)
        self.assertEqual(result.chainhook.uuid, "test-uuid-12345")
        self.assertIsInstance(result.chainhook.predicate, Predicate)
        self.assertEqual(result.chainhook.predicate.scope, "block_height")
        self.assertEqual(result.chainhook.predicate.higher_than, 123450)

        # Verify apply block structure
        self.assertEqual(len(result.apply), 1)
        apply_block = result.apply[0]
        self.assertIsInstance(apply_block, Apply)
        self.assertEqual(apply_block.block_identifier.hash, "0x1234567890abcdef")
        self.assertEqual(apply_block.block_identifier.index, 123456)
        self.assertEqual(apply_block.timestamp, 1640995200)

        # Verify parent block
        self.assertIsNotNone(apply_block.parent_block_identifier)
        self.assertEqual(apply_block.parent_block_identifier.hash, "0x0000000000000000")
        self.assertEqual(apply_block.parent_block_identifier.index, 123455)

        # Verify block metadata
        self.assertIsInstance(apply_block.metadata, BlockMetadata)
        self.assertEqual(apply_block.metadata.tenure_height, 12345)
        self.assertEqual(apply_block.metadata.pox_cycle_index, 123)

        # Verify transaction structure
        self.assertEqual(len(apply_block.transactions), 1)
        tx = apply_block.transactions[0]
        self.assertIsInstance(tx, TransactionWithReceipt)
        self.assertEqual(tx.transaction_identifier.hash, "0xabcdef1234567890")

        # Verify transaction metadata
        self.assertIsInstance(tx.metadata, TransactionMetadata)
        self.assertEqual(tx.metadata.description, "Test transaction")
        self.assertEqual(tx.metadata.fee, 1000)
        self.assertEqual(tx.metadata.nonce, 42)
        self.assertEqual(tx.metadata.sender, "ST1234567890ABCDEF")
        self.assertTrue(tx.metadata.success)

        # Verify transaction kind
        self.assertEqual(tx.metadata.kind.get("type"), "ContractCall")
        data = tx.metadata.kind.get("data", {})
        self.assertEqual(data.get("method"), "transfer")

        # Verify receipt
        self.assertIsInstance(tx.metadata.receipt, Receipt)
        self.assertEqual(len(tx.metadata.receipt.events), 1)
        event = tx.metadata.receipt.events[0]
        self.assertIsInstance(event, Event)
        self.assertEqual(event.type, "FTTransferEvent")
        self.assertEqual(event.data.get("amount"), "123456")

        # Verify operations
        self.assertEqual(len(tx.operations), 2)
        op = tx.operations[0]
        self.assertIsInstance(op, Operation)
        self.assertEqual(op.type, "DEBIT")
        self.assertEqual(op.status, "SUCCESS")
        self.assertEqual(op.account.get("address"), "ST1234567890ABCDEF")


if __name__ == "__main__":
    unittest.main()
