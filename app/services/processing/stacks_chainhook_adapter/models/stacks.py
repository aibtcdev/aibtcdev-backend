"""Stacks API data models for raw API responses."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass
class ExecutionCost:
    """Stacks API execution cost data."""

    read_count: int
    read_length: int
    runtime: int
    write_count: int
    write_length: int


@dataclass
class ContractCall:
    """Contract call data from Stacks API."""

    contract_id: str
    function_name: str
    function_signature: Optional[str] = None
    function_args: Optional[List[Dict[str, Any]]] = None


@dataclass
class StacksEvent:
    """Event data from Stacks API."""

    event_index: int
    event_type: str
    tx_id: str
    asset: Optional[Dict[str, Any]] = None
    contract_log: Optional[Dict[str, Any]] = None


@dataclass
class StacksTransaction:
    """Complete transaction data from Stacks API."""

    tx_id: str
    nonce: int
    fee_rate: str
    sender_address: str
    sponsored: bool
    post_condition_mode: str
    post_conditions: List[Any]
    anchor_mode: str
    tx_type: str
    tx_status: str
    block_hash: str
    block_height: int
    burn_block_time: int
    burn_block_time_iso: str
    canonical: bool
    microblock_canonical: bool
    microblock_sequence: int
    microblock_hash: str
    parent_microblock_hash: str
    tx_index: int
    tx_result: Dict[str, str]
    events: List[StacksEvent]
    execution_cost: Optional[ExecutionCost] = None
    contract_call: Optional[ContractCall] = None
    raw_tx: Optional[str] = None
    sponsor_address: Optional[str] = None


@dataclass
class StacksBlock:
    """Complete block data from Stacks API."""

    canonical: bool
    height: int
    hash: str
    index_block_hash: str
    parent_block_hash: str
    parent_index_block_hash: Optional[str]
    burn_block_time: int
    burn_block_time_iso: str
    burn_block_hash: str
    burn_block_height: int
    miner_txid: str
    txs: List[Union[str, StacksTransaction]]
    execution_cost_read_count: Optional[int] = None
    execution_cost_read_length: Optional[int] = None
    execution_cost_runtime: Optional[int] = None
    execution_cost_write_count: Optional[int] = None
    execution_cost_write_length: Optional[int] = None
    block_time: Optional[int] = None
    tenure_height: Optional[int] = None


@dataclass
class PoXCycle:
    """PoX cycle information."""

    id: int
    min_threshold_ustx: int
    stacked_ustx: int
    is_pox_active: bool


@dataclass
class PoXInfo:
    """PoX information from Stacks API."""

    contract_id: str
    pox_activation_threshold_ustx: int
    first_burnchain_block_height: int
    current_burnchain_block_height: int
    prepare_phase_block_length: int
    reward_phase_block_length: int
    reward_slots: int
    rejection_fraction: int
    total_liquid_supply_ustx: int
    current_cycle: PoXCycle
    next_cycle: PoXCycle
    min_amount_ustx: int
    prepare_cycle_length: int
    reward_cycle_id: int
    reward_cycle_length: int
    rejection_votes_left_required: int
    next_reward_cycle_in: int


@dataclass
class NetworkInfo:
    """Network information from Stacks API."""

    peer_version: int
    pox_consensus: str
    burn_block_height: int
    stable_pox_consensus: str
    stable_burn_block_height: int
    server_version: str
    network_id: int
    parent_network_id: int
    stacks_tip_height: int
    stacks_tip: str
    stacks_tip_consensus_hash: str
    genesis_txid: str
    unanchored_tip_height: int
    unanchored_tip: str
    unanchored_tip_consensus_hash: str
    exit_at_block_height: Optional[int] = None


@dataclass
class SignerInfo:
    """Signer information for Nakamoto blocks."""

    signer_bitvec: str
    signer_public_keys: List[str]
    signer_signature: List[str]
