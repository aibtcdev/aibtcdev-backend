"""Chainhook webhook parser implementation."""

import json
from typing import Any, Dict

from app.lib.logger import configure_logger
from app.services.integrations.webhooks.base import WebhookParser
from app.services.integrations.webhooks.chainhook.models import (
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


class ChainhookParser(WebhookParser):
    """Parser for Chainhook webhook payloads."""

    def __init__(self):
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def parse(self, raw_data: Dict[str, Any]) -> ChainHookData:
        """Parse Chainhook webhook data.

        Args:
            raw_data: The raw webhook payload

        Returns:
            ChainHookData: Structured data from the webhook
        """
        self.logger.debug("Parsing chainhook data")
        return self.parse_chainhook_payload(raw_data)

    def parse_chainhook_payload(self, payload: Dict[str, Any]) -> ChainHookData:
        """Parse a raw chainhook payload into structured data models.

        Args:
            payload: Raw dictionary from JSON payload

        Returns:
            ChainHookData object with structured data
        """
        self.logger.debug("Parsing chainhook payload")
        self.logger.debug(f"payload: {json.dumps(payload, indent=4)}")
        # Parse predicate
        predicate = Predicate(
            scope=payload.get("chainhook", {}).get("predicate", {}).get("scope", ""),
            higher_than=payload.get("chainhook", {})
            .get("predicate", {})
            .get("higher_than", 0),
        )

        # Parse chainhook info
        chainhook_info = ChainHookInfo(
            is_streaming_blocks=payload.get("chainhook", {}).get(
                "is_streaming_blocks", False
            ),
            predicate=predicate,
            uuid=payload.get("chainhook", {}).get("uuid", ""),
        )

        # Parse apply blocks
        apply_blocks = []
        for apply_data in payload.get("apply", []):
            # i need it pretty print json apply_data
            # self.logger.debug(f"apply_data: {json.dumps(apply_data, indent=4)}")
            # Parse block identifier
            block_id = BlockIdentifier(
                hash=apply_data.get("block_identifier", {}).get("hash", ""),
                index=apply_data.get("block_identifier", {}).get("index", 0),
            )

            parent_block_id = None
            if "parent_block_identifier" in apply_data:
                parent_block_id = BlockIdentifier(
                    hash=apply_data.get("parent_block_identifier", {}).get("hash", ""),
                    index=apply_data.get("parent_block_identifier", {}).get("index", 0),
                )

            # Parse block metadata
            block_metadata = None
            if "metadata" in apply_data:
                bitcoin_anchor = None
                if "bitcoin_anchor_block_identifier" in apply_data.get("metadata", {}):
                    bitcoin_anchor = BlockIdentifier(
                        hash=apply_data.get("metadata", {})
                        .get("bitcoin_anchor_block_identifier", {})
                        .get("hash", ""),
                        index=apply_data.get("metadata", {})
                        .get("bitcoin_anchor_block_identifier", {})
                        .get("index", 0),
                    )

                block_metadata = BlockMetadata(
                    bitcoin_anchor_block_identifier=bitcoin_anchor,
                    block_time=apply_data.get("metadata", {}).get("block_time"),
                    confirm_microblock_identifier=apply_data.get("metadata", {}).get(
                        "confirm_microblock_identifier"
                    ),
                    cycle_number=apply_data.get("metadata", {}).get("cycle_number"),
                    pox_cycle_index=apply_data.get("metadata", {}).get(
                        "pox_cycle_index"
                    ),
                    pox_cycle_length=apply_data.get("metadata", {}).get(
                        "pox_cycle_length"
                    ),
                    pox_cycle_position=apply_data.get("metadata", {}).get(
                        "pox_cycle_position"
                    ),
                    reward_set=apply_data.get("metadata", {}).get("reward_set"),
                    signer_bitvec=apply_data.get("metadata", {}).get("signer_bitvec"),
                    signer_public_keys=apply_data.get("metadata", {}).get(
                        "signer_public_keys"
                    ),
                    signer_signature=apply_data.get("metadata", {}).get(
                        "signer_signature"
                    ),
                    stacks_block_hash=apply_data.get("metadata", {}).get(
                        "stacks_block_hash"
                    ),
                    tenure_height=apply_data.get("metadata", {}).get("tenure_height"),
                )

            # Parse transactions
            transactions = []
            for tx_data in apply_data.get("transactions", []):
                tx_id = TransactionIdentifier(
                    hash=tx_data.get("transaction_identifier", {}).get("hash", "")
                )

                # Parse operations
                operations = []
                for op_data in tx_data.get("operations", []):
                    operations.append(
                        Operation(
                            account=op_data.get("account", {}),
                            amount=op_data.get("amount", {}),
                            operation_identifier=op_data.get(
                                "operation_identifier", {}
                            ),
                            status=op_data.get("status", ""),
                            type=op_data.get("type", ""),
                            related_operations=op_data.get("related_operations"),
                        )
                    )

                # Parse receipt events
                events = []
                for event_data in (
                    tx_data.get("metadata", {}).get("receipt", {}).get("events", [])
                ):
                    events.append(
                        Event(
                            data=event_data.get("data", {}),
                            position=event_data.get("position", {}),
                            type=event_data.get("type", ""),
                        )
                    )

                # Parse receipt
                receipt = Receipt(
                    contract_calls_stack=tx_data.get("metadata", {})
                    .get("receipt", {})
                    .get("contract_calls_stack", []),
                    events=events,
                    mutated_assets_radius=tx_data.get("metadata", {})
                    .get("receipt", {})
                    .get("mutated_assets_radius", []),
                    mutated_contracts_radius=tx_data.get("metadata", {})
                    .get("receipt", {})
                    .get("mutated_contracts_radius", []),
                )

                # Parse transaction metadata
                metadata = TransactionMetadata(
                    description=tx_data.get("metadata", {}).get("description", ""),
                    execution_cost=tx_data.get("metadata", {}).get(
                        "execution_cost", {}
                    ),
                    fee=tx_data.get("metadata", {}).get("fee", 0),
                    kind=tx_data.get("metadata", {}).get("kind", {}),
                    nonce=tx_data.get("metadata", {}).get("nonce", 0),
                    position=tx_data.get("metadata", {}).get("position", {}),
                    raw_tx=tx_data.get("metadata", {}).get("raw_tx", ""),
                    receipt=receipt,
                    result=tx_data.get("metadata", {}).get("result", ""),
                    sender=tx_data.get("metadata", {}).get("sender", ""),
                    sponsor=tx_data.get("metadata", {}).get("sponsor"),
                    success=tx_data.get("metadata", {}).get("success", False),
                )

                transactions.append(
                    TransactionWithReceipt(
                        transaction_identifier=tx_id,
                        metadata=metadata,
                        operations=operations,
                    )
                )

            apply_blocks.append(
                Apply(
                    block_identifier=block_id,
                    transactions=transactions,
                    metadata=block_metadata,
                    parent_block_identifier=parent_block_id,
                    timestamp=apply_data.get("timestamp"),
                )
            )

        # Create final ChainHookData object
        return ChainHookData(
            apply=apply_blocks,
            chainhook=chainhook_info,
            events=payload.get("events", []),
            rollback=payload.get("rollback", []),
        )
