"""Chainhook data models that match the exact format expected by handlers."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class BlockIdentifier:
    """Block identifier with hash and index."""

    hash: str
    index: int


@dataclass
class TransactionIdentifier:
    """Transaction identifier with hash."""

    hash: str


@dataclass
class Event:
    """Transaction event data."""

    data: Dict[str, Any]
    position: Dict[str, int]
    type: str


@dataclass
class Receipt:
    """Transaction receipt containing events and mutated data."""

    contract_calls_stack: List[Any]
    events: List[Event]
    mutated_assets_radius: List[str]
    mutated_contracts_radius: List[str]


@dataclass
class ExecutionCost:
    """Transaction execution cost metrics."""

    read_count: int
    read_length: int
    runtime: int
    write_count: int
    write_length: int


@dataclass
class TransactionKind:
    """Transaction kind data (e.g., ContractCall)."""

    data: Dict[str, Any]
    type: str


@dataclass
class TransactionMetadata:
    """Complete transaction metadata."""

    description: str
    execution_cost: ExecutionCost
    fee: int
    kind: TransactionKind
    nonce: int
    position: Dict[str, int]
    raw_tx: str
    receipt: Receipt
    result: str
    sender: str
    sponsor: Optional[str]
    success: bool


@dataclass
class OperationIdentifier:
    """Operation identifier."""

    index: int


@dataclass
class Account:
    """Account information for operations."""

    address: str


@dataclass
class Currency:
    """Currency information for operations."""

    decimals: int
    metadata: Dict[str, Any]
    symbol: str


@dataclass
class Amount:
    """Amount information for operations."""

    currency: Currency
    value: int


@dataclass
class Operation:
    """Transaction operation (e.g., DEBIT/CREDIT)."""

    account: Account
    amount: Amount
    operation_identifier: OperationIdentifier
    related_operations: List[Dict[str, int]]
    status: str
    type: str


@dataclass
class TransactionWithReceipt:
    """Complete transaction with receipt and operations."""

    metadata: TransactionMetadata
    operations: List[Operation]
    transaction_identifier: TransactionIdentifier


@dataclass
class Apply:
    """Apply block containing transactions and metadata."""

    block_identifier: BlockIdentifier
    metadata: Dict[str, Any]
    parent_block_identifier: BlockIdentifier
    timestamp: int
    transactions: List[TransactionWithReceipt]


@dataclass
class Predicate:
    """Chainhook predicate configuration."""

    scope: str
    equals: Optional[int] = None
    higher_than: Optional[int] = None
    lower_than: Optional[int] = None
    between: Optional[List[int]] = None


@dataclass
class ChainHookInfo:
    """Chainhook configuration information."""

    is_streaming_blocks: bool
    predicate: Predicate
    uuid: str


@dataclass
class ChainHookData:
    """Complete chainhook data structure."""

    apply: List[Apply]
    chainhook: ChainHookInfo
    events: List[Any]
    rollback: List[Any]
