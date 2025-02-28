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
