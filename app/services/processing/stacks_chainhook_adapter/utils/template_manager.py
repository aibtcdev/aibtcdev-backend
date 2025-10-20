#!/usr/bin/env python3
"""
Template Manager for Stacks Chainhook Adapter

This module uses real chainhook data files as templates to ensure 100%
structural compatibility. We clone the key-value structure and populate
with Stacks API data, setting null for unavailable values.
"""

import json
import os
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from copy import deepcopy

from ..models.chainhook import ChainHookData


class ChainhookTemplateManager:
    """
    Manages chainhook templates extracted from real chainhook data files.
    Ensures our adapter output matches the exact structure of real chainhooks.
    """

    def __init__(self, template_directory: str = "chainhook-data"):
        """
        Initialize with the directory containing chainhook template files.

        Args:
            template_directory: Directory containing chainhook JSON files
        """
        # Find template directory relative to project root
        if not os.path.isabs(template_directory):
            # Look for template directory starting from current file and going up
            current_dir = Path(__file__).parent
            project_root = None

            # Search up the directory tree for the template directory
            search_dir = current_dir
            for _ in range(10):  # Limit search to avoid infinite loop
                potential_template_dir = search_dir / template_directory
                if potential_template_dir.exists():
                    project_root = search_dir
                    break
                search_dir = search_dir.parent
                if search_dir == search_dir.parent:  # Reached root
                    break

            if project_root:
                self.template_directory = project_root / template_directory
            else:
                # Fallback to relative path
                self.template_directory = Path(template_directory)
        else:
            self.template_directory = Path(template_directory)

        self.templates = {}
        self.load_templates()

    def load_templates(self):
        """Load all chainhook template files."""
        print(f"🔍 Looking for templates in: {self.template_directory.absolute()}")

        if not self.template_directory.exists():
            print(f"❌ Template directory not found: {self.template_directory}")
            return

        print(f"✅ Template directory found: {self.template_directory}")

        # List what's actually in the directory
        try:
            files_in_dir = list(self.template_directory.glob("*.json"))
            print(f"📁 JSON files found: {[f.name for f in files_in_dir]}")
        except Exception as e:
            print(f"❌ Error listing directory contents: {e}")

        template_files = {
            "buy-and-deposit": "buy-and-deposit.json",
            "conclude-action-proposal": "conclude-action-proposal.json",
            "create-action-proposal": "create-action-proposal.json",
            "send-many-governance-airdrop": "send-many-governance-airdrop.json",
            "send-many-stx-airdrop": "send-many-stx-airdrop.json",
            "vote-on-action-proposal": "vote-on-action-proposal.json",
            "coinbase": "coinbase-block.json",
        }

        for template_name, filename in template_files.items():
            file_path = self.template_directory / filename
            if file_path.exists():
                try:
                    with open(file_path, "r") as f:
                        template_data = json.load(f)
                        self.templates[template_name] = template_data
                        print(f"✅ Loaded template: {template_name}")
                except Exception as e:
                    print(f"❌ Failed to load template {filename}: {e}")
            else:
                print(f"⚠️  Template file not found: {filename}")

    def get_template_for_transaction_type(
        self, transaction_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the appropriate template for a transaction type.

        Args:
            transaction_type: The detected transaction type

        Returns:
            Template dictionary or None if not found
        """
        # Map transaction types to template names
        type_mapping = {
            "buy-and-deposit": "buy-and-deposit",
            "conclude-action-proposal": "conclude-action-proposal",
            "create-action-proposal": "create-action-proposal",
            "send-many-governance-airdrop": "send-many-governance-airdrop",
            "send-many-stx-airdrop": "send-many-stx-airdrop",
            "vote-on-action-proposal": "vote-on-action-proposal",
            "coinbase": "coinbase",  # Use coinbase template for tenure change + coinbase blocks
            "multi-vote-on-action-proposal": "vote-on-action-proposal",  # Use single vote template
            "governance-and-airdrop-multi-tx": "send-many-governance-airdrop",  # Use airdrop template
            "set-dao-charter": "conclude-action-proposal",  # Use conclude template as fallback for charter updates
        }

        template_name = type_mapping.get(transaction_type)
        if template_name and template_name in self.templates:
            return deepcopy(self.templates[template_name])

        # Fallback to a generic template (use conclude-action-proposal as base)
        if "conclude-action-proposal" in self.templates:
            return deepcopy(self.templates["conclude-action-proposal"])

        return None

    def populate_template(
        self,
        template: Dict[str, Any],
        chainhook_data: ChainHookData,
        transaction_type: str,
    ) -> Dict[str, Any]:
        """
        Populate a chainhook template with actual Stacks API data.

        Args:
            template: The chainhook template to populate
            chainhook_data: Our adapter's chainhook data
            transaction_type: The detected transaction type

        Returns:
            Populated template matching original chainhook structure
        """
        if not template or not chainhook_data or not chainhook_data.apply:
            return template

        adapter_block = chainhook_data.apply[0]

        # Populate the apply section
        if "apply" in template and template["apply"]:
            template_apply = template["apply"][0]

            # Update block identifier
            if "block_identifier" in template_apply:
                template_apply["block_identifier"]["hash"] = (
                    adapter_block.block_identifier.hash
                )
                template_apply["block_identifier"]["index"] = (
                    adapter_block.block_identifier.index
                )

            # Update parent block identifier
            if "parent_block_identifier" in template_apply:
                template_apply["parent_block_identifier"]["hash"] = (
                    adapter_block.parent_block_identifier.hash
                )
                template_apply["parent_block_identifier"]["index"] = (
                    adapter_block.parent_block_identifier.index
                )

            # Update timestamp
            if "timestamp" in template_apply:
                template_apply["timestamp"] = adapter_block.timestamp

            # Update metadata (keep template structure, update available values)
            if "metadata" in template_apply and adapter_block.metadata:
                self._populate_metadata(
                    template_apply["metadata"], adapter_block.metadata
                )

            # Update transactions (most complex part)
            if "transactions" in template_apply and adapter_block.transactions:
                self._populate_transactions(
                    template_apply["transactions"], adapter_block.transactions
                )

        # Update chainhook section
        if "chainhook" in template:
            template["chainhook"]["uuid"] = str(uuid.uuid4())
            if "predicate" in template["chainhook"]:
                template["chainhook"]["predicate"]["equals"] = (
                    adapter_block.block_identifier.index
                )

        # Keep events and rollback as empty arrays (matching original)
        template["events"] = []
        template["rollback"] = []

        return template

    def _populate_metadata(
        self, template_metadata: Dict[str, Any], adapter_metadata: Any
    ):
        """Populate block metadata while preserving template structure."""
        # Handle both dict and object-style metadata
        if isinstance(adapter_metadata, dict):
            # Metadata is a dictionary (from adapter)
            if "bitcoin_anchor_block_identifier" in adapter_metadata:
                if "bitcoin_anchor_block_identifier" in template_metadata:
                    bitcoin_anchor = adapter_metadata["bitcoin_anchor_block_identifier"]
                    template_metadata["bitcoin_anchor_block_identifier"]["index"] = (
                        bitcoin_anchor["index"]
                    )
                    template_metadata["bitcoin_anchor_block_identifier"]["hash"] = (
                        bitcoin_anchor["hash"]
                    )
                    # Use debug logging instead of print
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"Template manager: Updated bitcoin_anchor_block_identifier to index={bitcoin_anchor['index']}"
                    )
        else:
            # Metadata is a dataclass object (fallback)
            if hasattr(adapter_metadata, "bitcoin_anchor_block_identifier"):
                if "bitcoin_anchor_block_identifier" in template_metadata:
                    template_metadata["bitcoin_anchor_block_identifier"]["index"] = (
                        adapter_metadata.bitcoin_anchor_block_identifier.index
                    )
                    template_metadata["bitcoin_anchor_block_identifier"]["hash"] = (
                        adapter_metadata.bitcoin_anchor_block_identifier.hash
                    )

        # Handle other metadata fields for both dict and object formats
        metadata_fields = [
            "block_time",
            "pox_cycle_index",
            "pox_cycle_length",
            "pox_cycle_position",
            "tenure_height",
            "stacks_block_hash",
        ]

        for field in metadata_fields:
            if isinstance(adapter_metadata, dict):
                if field in adapter_metadata:
                    template_metadata[field] = adapter_metadata[field]
            else:
                if hasattr(adapter_metadata, field):
                    template_metadata[field] = getattr(adapter_metadata, field)

        # Handle signer fields - preserve original template values if adapter doesn't have real data
        signer_fields = ["signer_bitvec", "signer_public_keys", "signer_signature"]
        for field in signer_fields:
            if field in template_metadata:
                if isinstance(adapter_metadata, dict):
                    adapter_value = adapter_metadata.get(field, "")
                else:
                    adapter_value = getattr(adapter_metadata, field, "")

                if field == "signer_bitvec":
                    # Only use if it looks like real signer data
                    if adapter_value and str(adapter_value).startswith("0"):
                        template_metadata[field] = adapter_value
                    # Otherwise keep original template value
                elif field in ["signer_public_keys", "signer_signature"]:
                    # Only use if we have actual data
                    if adapter_value:
                        template_metadata[field] = adapter_value
                    # Otherwise keep original template value

    def _populate_transactions(
        self, template_transactions: List[Dict], adapter_transactions: List
    ):
        """Populate transaction array while preserving template structure."""
        # Handle different numbers of transactions
        if len(adapter_transactions) == len(template_transactions):
            # Same count - update each transaction
            for i, (template_tx, adapter_tx) in enumerate(
                zip(template_transactions, adapter_transactions)
            ):
                self._populate_single_transaction(template_tx, adapter_tx)

        elif len(adapter_transactions) < len(template_transactions):
            # Fewer adapter transactions - populate what we can, null the rest
            for i, adapter_tx in enumerate(adapter_transactions):
                if i < len(template_transactions):
                    self._populate_single_transaction(
                        template_transactions[i], adapter_tx
                    )

            # Remove extra template transactions
            template_transactions[:] = template_transactions[
                : len(adapter_transactions)
            ]

        else:
            # More adapter transactions - use template structure for all
            # Keep original template transactions and duplicate structure for extras
            original_count = len(template_transactions)

            # Populate existing template transactions
            for i in range(original_count):
                if i < len(adapter_transactions):
                    self._populate_single_transaction(
                        template_transactions[i], adapter_transactions[i]
                    )

            # Add additional transactions using the first template as a model
            if template_transactions:
                base_template = deepcopy(template_transactions[0])
                for i in range(original_count, len(adapter_transactions)):
                    new_tx = deepcopy(base_template)
                    self._populate_single_transaction(new_tx, adapter_transactions[i])
                    template_transactions.append(new_tx)

    def _populate_single_transaction(
        self, template_tx: Dict[str, Any], adapter_tx: Any
    ):
        """Populate a single transaction while preserving template structure."""
        if not hasattr(adapter_tx, "metadata") or not adapter_tx.metadata:
            return

        metadata = adapter_tx.metadata

        # Update transaction identifier
        if "transaction_identifier" in template_tx:
            template_tx["transaction_identifier"]["hash"] = (
                adapter_tx.transaction_identifier.hash
            )

        # Update metadata section
        if "metadata" in template_tx:
            template_metadata = template_tx["metadata"]

            # Basic fields
            template_metadata["description"] = getattr(metadata, "description", "")
            template_metadata["success"] = getattr(metadata, "success", True)
            template_metadata["result"] = getattr(metadata, "result", "(ok true)")
            template_metadata["fee"] = getattr(metadata, "fee", 0)
            template_metadata["nonce"] = getattr(metadata, "nonce", 0)
            template_metadata["sender"] = getattr(metadata, "sender", "")
            template_metadata["sponsor"] = getattr(metadata, "sponsor", None)

            # Execution cost
            if "execution_cost" in template_metadata and hasattr(
                metadata, "execution_cost"
            ):
                exec_cost = metadata.execution_cost
                template_metadata["execution_cost"]["read_count"] = getattr(
                    exec_cost, "read_count", 0
                )
                template_metadata["execution_cost"]["read_length"] = getattr(
                    exec_cost, "read_length", 0
                )
                template_metadata["execution_cost"]["runtime"] = getattr(
                    exec_cost, "runtime", 0
                )
                template_metadata["execution_cost"]["write_count"] = getattr(
                    exec_cost, "write_count", 0
                )
                template_metadata["execution_cost"]["write_length"] = getattr(
                    exec_cost, "write_length", 0
                )

            # Transaction kind (ContractCall, TokenTransfer, etc.)
            if "kind" in template_metadata and hasattr(metadata, "kind"):
                kind = metadata.kind
                if hasattr(kind, "type"):
                    template_metadata["kind"]["type"] = kind.type
                    if hasattr(kind, "data") and "data" in template_metadata["kind"]:
                        kind_data = kind.data
                        # Handle both dict and dataclass access patterns
                        if isinstance(kind_data, dict):
                            template_metadata["kind"]["data"]["contract_identifier"] = (
                                kind_data.get("contract_identifier", "")
                            )
                            template_metadata["kind"]["data"]["method"] = kind_data.get(
                                "method", ""
                            )
                            template_metadata["kind"]["data"]["args"] = kind_data.get(
                                "args", []
                            )
                        else:
                            template_metadata["kind"]["data"]["contract_identifier"] = (
                                getattr(kind_data, "contract_identifier", "")
                            )
                            template_metadata["kind"]["data"]["method"] = getattr(
                                kind_data, "method", ""
                            )
                            template_metadata["kind"]["data"]["args"] = getattr(
                                kind_data, "args", []
                            )

            # Position
            if "position" in template_metadata:
                template_metadata["position"]["index"] = getattr(
                    metadata, "position", {}
                ).get("index", 0)

            # Raw transaction - preserve original template value if our adapter doesn't have it
            if "raw_tx" in template_metadata:
                adapter_raw_tx = getattr(metadata, "raw_tx", "")
                if adapter_raw_tx and adapter_raw_tx != "0x":
                    template_metadata["raw_tx"] = adapter_raw_tx
                # If adapter doesn't have raw_tx, keep the original template value

            # Receipt (events, mutations, etc.)
            if "receipt" in template_metadata and hasattr(metadata, "receipt"):
                self._populate_receipt(template_metadata["receipt"], metadata.receipt)

        # Update operations
        if "operations" in template_tx and hasattr(adapter_tx, "operations"):
            self._populate_operations(template_tx["operations"], adapter_tx.operations)

    def _populate_receipt(self, template_receipt: Dict[str, Any], adapter_receipt: Any):
        """Populate transaction receipt."""
        if not adapter_receipt:
            return

        # Contract calls stack
        if "contract_calls_stack" in template_receipt:
            template_receipt["contract_calls_stack"] = getattr(
                adapter_receipt, "contract_calls_stack", []
            )

        # Events
        if "events" in template_receipt and hasattr(adapter_receipt, "events"):
            template_receipt["events"] = []
            for event in adapter_receipt.events:
                event_dict = {
                    "data": getattr(event, "data", {}),
                    "position": getattr(event, "position", {"index": 0}),
                    "type": getattr(event, "type", "SmartContractEvent"),
                }
                template_receipt["events"].append(event_dict)

        # Mutated assets and contracts
        if "mutated_assets_radius" in template_receipt:
            template_receipt["mutated_assets_radius"] = getattr(
                adapter_receipt, "mutated_assets_radius", []
            )
        if "mutated_contracts_radius" in template_receipt:
            template_receipt["mutated_contracts_radius"] = getattr(
                adapter_receipt, "mutated_contracts_radius", []
            )

    def _populate_operations(
        self, template_operations: List[Dict], adapter_operations: List
    ):
        """Populate operations array."""
        template_operations.clear()  # Clear existing operations

        for i, operation in enumerate(adapter_operations):
            op_dict = {
                "account": {"address": getattr(operation.account, "address", "")},
                "amount": {
                    "currency": {
                        "decimals": getattr(operation.amount.currency, "decimals", 6),
                        "symbol": getattr(operation.amount.currency, "symbol", "TOKEN"),
                        "metadata": getattr(operation.amount.currency, "metadata", {}),
                    },
                    "value": getattr(operation.amount, "value", 0),
                },
                "operation_identifier": {"index": i},
                "related_operations": getattr(operation, "related_operations", []),
                "status": getattr(operation, "status", "SUCCESS"),
                "type": getattr(operation, "type", "CREDIT"),
            }
            template_operations.append(op_dict)

    def generate_chainhook_from_template(
        self, chainhook_data: ChainHookData, transaction_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a chainhook-compatible output using templates.

        Args:
            chainhook_data: Our adapter's chainhook data
            transaction_type: The detected transaction type

        Returns:
            Template-based chainhook data matching original structure
        """
        template = self.get_template_for_transaction_type(transaction_type)
        if not template:
            print(f"⚠️  No template found for transaction type: {transaction_type}")
            return None

        populated_template = self.populate_template(
            template, chainhook_data, transaction_type
        )

        # No extra metadata - must match chainhook model 100%
        return populated_template


# Global template manager instance
_template_manager = None


def get_template_manager() -> ChainhookTemplateManager:
    """Get the global template manager instance."""
    global _template_manager
    if _template_manager is None:
        _template_manager = ChainhookTemplateManager()
    return _template_manager
