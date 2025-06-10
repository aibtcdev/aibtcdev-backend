"""Chainhook webhook data models."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

# Configure logger
logger = logging.getLogger(__name__)


@dataclass
class TransactionIdentifier:
    """Transaction identifier with hash."""

    hash: str


@dataclass
class BlockIdentifier:
    """Block identifier with hash and index."""

    hash: str
    index: int


@dataclass
class Operation:
    """Operation within a transaction."""

    account: Dict[str, str]
    amount: Dict[str, Any]
    operation_identifier: Dict[str, int]
    status: str
    type: str
    related_operations: Optional[List[Dict[str, int]]] = None


@dataclass
class Event:
    """Event data from transaction receipt."""

    data: Dict[str, Any]
    position: Dict[str, int]
    type: str


@dataclass
class Receipt:
    """Transaction receipt containing events and other metadata."""

    contract_calls_stack: List[Any]
    events: List[Event]
    mutated_assets_radius: List[Any]
    mutated_contracts_radius: List[Any]


@dataclass
class TransactionMetadata:
    """Metadata about a transaction including execution cost and kind."""

    description: str
    execution_cost: Dict[str, int]
    fee: int
    kind: Dict[str, Any]
    nonce: int
    position: Dict[str, int]
    raw_tx: str
    receipt: Receipt
    result: str
    sender: str
    sponsor: Optional[str]
    success: bool


@dataclass
class TransactionWithReceipt:
    """Transaction with receipt including metadata and operations."""

    transaction_identifier: TransactionIdentifier
    metadata: Union[Dict[str, Any], TransactionMetadata]
    operations: List[Union[Dict[str, Any], Operation]]


@dataclass
class BlockMetadata:
    """Metadata about a block."""

    bitcoin_anchor_block_identifier: Optional[BlockIdentifier] = None
    block_time: Optional[int] = None
    confirm_microblock_identifier: Optional[Any] = None
    cycle_number: Optional[int] = None
    pox_cycle_index: Optional[int] = None
    pox_cycle_length: Optional[int] = None
    pox_cycle_position: Optional[int] = None
    reward_set: Optional[Any] = None
    signer_bitvec: Optional[str] = None
    signer_public_keys: Optional[List[str]] = None
    signer_signature: Optional[List[str]] = None
    stacks_block_hash: Optional[str] = None
    tenure_height: Optional[int] = None


@dataclass
class Apply:
    """Apply block data structure containing transactions."""

    block_identifier: BlockIdentifier
    transactions: List[TransactionWithReceipt]
    metadata: Optional[BlockMetadata] = None
    parent_block_identifier: Optional[BlockIdentifier] = None
    timestamp: Optional[int] = None


@dataclass
class Predicate:
    """Predicate for chainhook filter."""

    scope: str
    higher_than: int


@dataclass
class ChainHookInfo:
    """Information about the chainhook itself."""

    is_streaming_blocks: bool
    predicate: Predicate
    uuid: str


@dataclass
class ChainHookData:
    """Top-level data structure for Chainhook webhook payloads."""

    apply: List[Apply]
    chainhook: ChainHookInfo
    events: List[Any]
    rollback: List[Any]


# V2 API models for block transactions


@dataclass
class Principal:
    """Principal for post condition."""

    type_id: str


@dataclass
class PostCondition:
    """Post condition in a transaction."""

    principal: Principal
    condition_code: str
    amount: str
    type: str


@dataclass
class ClarityValue:
    """Clarity value representation."""

    hex: str
    repr: str


@dataclass
class ContractLog:
    """Contract log in an event."""

    contract_id: str
    topic: str
    value: ClarityValue


@dataclass
class TransactionEvent:
    """Event in a transaction."""

    event_index: int
    event_type: str
    tx_id: str
    contract_log: Optional[ContractLog] = None


@dataclass
class TokenTransfer:
    """Token transfer details."""

    recipient_address: str
    amount: str
    memo: Optional[str] = None


@dataclass
class BlockTransaction:
    """Transaction in a block."""

    tx_id: str
    nonce: int
    fee_rate: str
    sender_address: str
    post_condition_mode: str
    post_conditions: List[PostCondition]
    anchor_mode: str
    block_hash: str
    block_height: int
    block_time: int
    block_time_iso: str
    burn_block_height: int
    burn_block_time: int
    burn_block_time_iso: str
    parent_burn_block_time: int
    parent_burn_block_time_iso: str
    canonical: bool
    tx_index: int
    tx_status: str
    tx_result: ClarityValue
    event_count: int
    parent_block_hash: str
    is_unanchored: bool
    execution_cost_read_count: int
    execution_cost_read_length: int
    execution_cost_runtime: int
    execution_cost_write_count: int
    execution_cost_write_length: int
    events: List[TransactionEvent]
    tx_type: str
    sponsor_nonce: Optional[int] = None
    sponsored: Optional[bool] = None
    sponsor_address: Optional[str] = None
    microblock_hash: Optional[str] = None
    microblock_sequence: Optional[int] = None
    microblock_canonical: Optional[bool] = None
    token_transfer: Optional[TokenTransfer] = None


@dataclass
class BlockTransactionsResponse:
    """Response from the block transactions API."""

    limit: int
    offset: int
    total: int
    results: List[BlockTransaction]


@dataclass
class ChainTip:
    """Current chain tip information."""

    block_height: int
    block_hash: str
    index_block_hash: str
    microblock_hash: str
    microblock_sequence: int
    burn_block_height: int


@dataclass
class HiroApiInfo:
    """Hiro API server information."""

    server_version: str
    status: str
    pox_v1_unlock_height: int
    pox_v2_unlock_height: int
    pox_v3_unlock_height: int
    chain_tip: Union[ChainTip, Dict[str, Any]]

    def __post_init__(self):
        """Convert chain_tip from dict to ChainTip object if needed."""
        # If chain_tip is a dictionary, convert it to a ChainTip object
        if isinstance(self.chain_tip, dict) and not isinstance(
            self.chain_tip, ChainTip
        ):
            # Some implementations might only include a subset of fields
            self.chain_tip = ChainTip(
                block_height=self.chain_tip.get("block_height", 0),
                block_hash=self.chain_tip.get("block_hash", ""),
                index_block_hash=self.chain_tip.get("index_block_hash", ""),
                microblock_hash=self.chain_tip.get("microblock_hash", ""),
                microblock_sequence=self.chain_tip.get("microblock_sequence", 0),
                burn_block_height=self.chain_tip.get("burn_block_height", 0),
            )
