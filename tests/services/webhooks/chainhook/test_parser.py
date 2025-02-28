"""Tests for the chainhook parser."""

import unittest
from typing import Any, Dict

from services.webhooks.chainhook.models import ChainHookData
from services.webhooks.chainhook.parser import ChainhookParser


class TestChainhookParser(unittest.TestCase):
    """Test cases for ChainhookParser."""

    def setUp(self):
        """Set up the test environment."""
        self.parser = ChainhookParser()

        # Sample data for testing
        self.sample_data: Dict[str, Any] = {
            "apply": [
                {
                    "block_identifier": {"hash": "0x1234567890abcdef", "index": 123456},
                    "transactions": [
                        {
                            "transaction_identifier": {"hash": "0xabcdef1234567890"},
                            "metadata": {
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
                            "operations": [],
                        }
                    ],
                }
            ]
        }

    def test_parse(self):
        """Test parsing chainhook webhook data."""
        result = self.parser.parse(self.sample_data)

        # Verify the result is of the correct type
        self.assertIsInstance(result, ChainHookData)

        # Verify the parsed data structure
        self.assertEqual(len(result.apply), 1)
        self.assertEqual(result.apply[0].block_identifier.hash, "0x1234567890abcdef")
        self.assertEqual(result.apply[0].block_identifier.index, 123456)

        # Verify transaction data
        self.assertEqual(len(result.apply[0].transactions), 1)
        tx = result.apply[0].transactions[0]
        self.assertEqual(tx.transaction_identifier.hash, "0xabcdef1234567890")
        self.assertEqual(tx.metadata["sender"], "ST1234567890ABCDEF")

        # Verify metadata structure
        kind = tx.metadata.get("kind", {})
        self.assertEqual(kind.get("type"), "ContractCall")

        # Verify data structure
        data = kind.get("data", {})
        self.assertEqual(data.get("method"), "send")
        self.assertEqual(data.get("args"), ["test message"])


if __name__ == "__main__":
    unittest.main()
