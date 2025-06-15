"""Hiro API specific data models."""

from dataclasses import dataclass
from typing import Any, Dict, List, Union, Optional


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
