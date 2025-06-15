"""Chain state monitoring task implementation."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.factory import backend
from config import config
from services.integrations.hiro.hiro_api import HiroApi
from lib.logger import configure_logger
from services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from services.infrastructure.job_management.decorators import JobPriority, job
from services.integrations.webhooks.chainhook import ChainhookService
from services.integrations.webhooks.chainhook.models import (
    Apply,
    BlockIdentifier,
    BlockMetadata,
    ChainHookData,
    ChainHookInfo,
    Predicate,
    TransactionIdentifier,
    TransactionWithReceipt,
)

logger = configure_logger(__name__)


@dataclass
class ChainStateMonitorResult(RunnerResult):
    """Result of chain state monitoring operation."""

    network: str = None
    is_stale: bool = False
    last_updated: Optional[datetime] = None
    elapsed_minutes: float = 0
    blocks_behind: int = 0
    blocks_processed: Optional[List[int]] = None

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.network is None:
            self.network = config.network.network
        if self.blocks_processed is None:
            self.blocks_processed = []


@job(
    job_type="chain_state_monitor",
    name="Chain State Monitor",
    description="Monitors blockchain state for synchronization with enhanced monitoring and error handling",
    interval_seconds=90,  # 1.5 minutes
    priority=JobPriority.MEDIUM,
    max_retries=3,
    retry_delay_seconds=120,
    timeout_seconds=300,
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=20,
    enable_dead_letter_queue=True,
)
class ChainStateMonitorTask(BaseTask[ChainStateMonitorResult]):
    """Task for monitoring blockchain state and syncing with database with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self.hiro_api = HiroApi()
        self.chainhook_service = ChainhookService()

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Chain state monitor doesn't require wallet configuration
            # It only reads from the blockchain, no transactions needed
            return True
        except Exception as e:
            logger.error(
                f"Error validating chain state monitor config: {str(e)}", exc_info=True
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for blockchain monitoring."""
        try:
            # Test HiroApi initialization and connectivity
            hiro_api = HiroApi()
            api_info = await hiro_api.aget_info()
            if not api_info:
                logger.error("Cannot connect to Hiro API")
                return False

            return True
        except Exception as e:
            logger.error(f"Resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Always valid to run - we want to check chain state freshness
            # even when there's no new data
            return True
        except Exception as e:
            logger.error(
                f"Error validating chain state monitor task: {str(e)}", exc_info=True
            )
            return False

    def _convert_to_chainhook_format(
        self,
        block_height: int,
        block_hash: str,
        parent_hash: str,
        transactions: Any,
        burn_block_height: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Convert block transactions to chainhook format.

        Args:
            block_height: Height of the block
            block_hash: Hash of the block
            parent_hash: Hash of the parent block
            transactions: Block transactions from Hiro API
            burn_block_height: Bitcoin burn block height (optional)

        Returns:
            Dict formatted as a chainhook webhook payload
        """
        # Get detailed block information from API
        try:
            block_data = self.hiro_api.get_block_by_height(block_height)
            logger.debug(
                f"Retrieved block data for height {block_height}: {block_data}"
            )
        except Exception as e:
            logger.warning(
                f"Could not fetch detailed block data for height {block_height}: {e}"
            )
            block_data = {}

        # Create block identifier
        block_identifier = BlockIdentifier(hash=block_hash, index=block_height)

        # Create parent block identifier
        parent_block_identifier = BlockIdentifier(
            hash=parent_hash, index=block_height - 1
        )

        # Extract block time from block data or transaction data, fallback to current time
        block_time = None
        if isinstance(block_data, dict):
            block_time = block_data.get("block_time")
        elif hasattr(block_data, "block_time"):
            block_time = block_data.block_time

        # If block_time not available from block data, try from first transaction
        if not block_time and transactions.results:
            tx = transactions.results[0]
            if isinstance(tx, dict):
                block_time = tx.get("block_time")
            else:
                block_time = getattr(tx, "block_time", None)

        # Fallback to current timestamp if still not found
        if not block_time:
            block_time = int(datetime.now().timestamp())
            logger.warning(
                f"Using current timestamp for block {block_height} as block_time was not available"
            )

        # Create comprehensive metadata with all available fields
        metadata = BlockMetadata(
            block_time=block_time,
            stacks_block_hash=block_hash,
        )

        # Extract additional metadata from block data if available
        if isinstance(block_data, dict):
            # Bitcoin anchor block identifier with proper hash
            bitcoin_anchor_info = block_data.get("bitcoin_anchor_block_identifier", {})
            bitcoin_anchor_hash = (
                bitcoin_anchor_info.get("hash", "")
                if isinstance(bitcoin_anchor_info, dict)
                else ""
            )
            if burn_block_height is not None:
                metadata.bitcoin_anchor_block_identifier = BlockIdentifier(
                    hash=bitcoin_anchor_hash, index=burn_block_height
                )

            # PoX cycle information
            pox_cycle_index = block_data.get("pox_cycle_index")
            if pox_cycle_index is not None:
                metadata.pox_cycle_index = pox_cycle_index

            pox_cycle_length = block_data.get("pox_cycle_length")
            if pox_cycle_length is not None:
                metadata.pox_cycle_length = pox_cycle_length

            pox_cycle_position = block_data.get("pox_cycle_position")
            if pox_cycle_position is not None:
                metadata.pox_cycle_position = pox_cycle_position

            cycle_number = block_data.get("cycle_number")
            if cycle_number is not None:
                metadata.cycle_number = cycle_number

            # Signer information
            signer_bitvec = block_data.get("signer_bitvec")
            if signer_bitvec is not None:
                metadata.signer_bitvec = signer_bitvec

            signer_public_keys = block_data.get("signer_public_keys")
            if signer_public_keys is not None:
                metadata.signer_public_keys = signer_public_keys

            signer_signature = block_data.get("signer_signature")
            if signer_signature is not None:
                metadata.signer_signature = signer_signature

            # Other metadata
            tenure_height = block_data.get("tenure_height")
            if tenure_height is not None:
                metadata.tenure_height = tenure_height

            confirm_microblock_identifier = block_data.get(
                "confirm_microblock_identifier"
            )
            if confirm_microblock_identifier is not None:
                metadata.confirm_microblock_identifier = confirm_microblock_identifier

            reward_set = block_data.get("reward_set")
            if reward_set is not None:
                metadata.reward_set = reward_set
        elif burn_block_height is not None:
            # Fallback: create basic bitcoin anchor block identifier without hash
            metadata.bitcoin_anchor_block_identifier = BlockIdentifier(
                hash="", index=burn_block_height
            )

        # Convert transactions to chainhook format with enhanced data
        chainhook_transactions = []
        for tx in transactions.results:
            # Handle tx as either dict or object
            if isinstance(tx, dict):
                tx_id = tx.get("tx_id", "")
                exec_cost_read_count = tx.get("execution_cost_read_count", 0)
                exec_cost_read_length = tx.get("execution_cost_read_length", 0)
                exec_cost_runtime = tx.get("execution_cost_runtime", 0)
                exec_cost_write_count = tx.get("execution_cost_write_count", 0)
                exec_cost_write_length = tx.get("execution_cost_write_length", 0)
                fee_rate = tx.get("fee_rate", "0")
                nonce = tx.get("nonce", 0)
                tx_index = tx.get("tx_index", 0)
                sender_address = tx.get("sender_address", "")
                sponsor_address = tx.get("sponsor_address", None)
                tx.get("sponsored", False)
                tx_status = tx.get("tx_status", "")
                tx_type = tx.get("tx_type", "")
                tx_result_repr = (
                    tx.get("tx_result", {}).get("repr", "")
                    if isinstance(tx.get("tx_result"), dict)
                    else ""
                )
                # Extract events and additional transaction data
                events = tx.get("events", [])
                raw_tx = tx.get("raw_tx", "")

                # Create better description based on transaction type and data
                description = self._create_transaction_description(tx)

                # Extract token transfer data if available
                token_transfer = tx.get("token_transfer")
            else:
                tx_id = tx.tx_id
                exec_cost_read_count = tx.execution_cost_read_count
                exec_cost_read_length = tx.execution_cost_read_length
                exec_cost_runtime = tx.execution_cost_runtime
                exec_cost_write_count = tx.execution_cost_write_count
                exec_cost_write_length = tx.execution_cost_write_length
                fee_rate = tx.fee_rate
                nonce = tx.nonce
                tx_index = tx.tx_index
                sender_address = tx.sender_address
                sponsor_address = tx.sponsor_address if tx.sponsored else None
                tx_status = tx.tx_status
                tx_type = tx.tx_type
                tx_result_repr = (
                    tx.tx_result.repr if hasattr(tx.tx_result, "repr") else ""
                )
                events = getattr(tx, "events", [])
                raw_tx = getattr(tx, "raw_tx", "")

                # Create better description
                description = self._create_transaction_description(tx)

                # Extract token transfer data
                token_transfer = getattr(tx, "token_transfer", None)

            # Create transaction identifier
            tx_identifier = TransactionIdentifier(hash=tx_id)

            # Convert events to proper format
            receipt_events = []
            for event in events:
                if isinstance(event, dict):
                    receipt_events.append(
                        {
                            "data": event.get("data", {}),
                            "position": {"index": event.get("event_index", 0)},
                            "type": event.get("event_type", ""),
                        }
                    )
                else:
                    receipt_events.append(
                        {
                            "data": getattr(event, "data", {}),
                            "position": {"index": getattr(event, "event_index", 0)},
                            "type": getattr(event, "event_type", ""),
                        }
                    )

            # Create transaction metadata with proper receipt
            tx_metadata = {
                "description": description,
                "execution_cost": {
                    "read_count": exec_cost_read_count,
                    "read_length": exec_cost_read_length,
                    "runtime": exec_cost_runtime,
                    "write_count": exec_cost_write_count,
                    "write_length": exec_cost_write_length,
                },
                "fee": (
                    int(fee_rate)
                    if isinstance(fee_rate, str) and fee_rate.isdigit()
                    else int(fee_rate)
                    if isinstance(fee_rate, (int, float))
                    else 0
                ),
                "kind": {"type": tx_type},
                "nonce": nonce,
                "position": {"index": tx_index},
                "raw_tx": raw_tx,
                "receipt": {
                    "contract_calls_stack": [],
                    "events": receipt_events,
                    "mutated_assets_radius": [],
                    "mutated_contracts_radius": [],
                },
                "result": tx_result_repr,
                "sender": sender_address,
                "sponsor": sponsor_address,
                "success": tx_status == "success",
            }

            # Generate operations based on transaction type and data
            operations = self._create_transaction_operations(tx, token_transfer)

            # Create transaction with receipt
            tx_with_receipt = TransactionWithReceipt(
                transaction_identifier=tx_identifier,
                metadata=tx_metadata,
                operations=operations,
            )

            chainhook_transactions.append(tx_with_receipt)

        # Create apply block
        apply_block = Apply(
            block_identifier=block_identifier,
            parent_block_identifier=parent_block_identifier,
            metadata=metadata,
            timestamp=block_time,
            transactions=chainhook_transactions,
        )

        # Create predicate
        predicate = Predicate(scope="block_height", higher_than=block_height - 1)

        # Create chainhook info
        chainhook_info = ChainHookInfo(
            is_streaming_blocks=False, predicate=predicate, uuid=str(uuid.uuid4())
        )

        # Create full chainhook data
        ChainHookData(
            apply=[apply_block], chainhook=chainhook_info, events=[], rollback=[]
        )

        # Convert to dict for webhook processing with complete metadata
        metadata_dict = {
            "block_time": apply_block.metadata.block_time,
            "stacks_block_hash": apply_block.metadata.stacks_block_hash,
        }

        # Add all available metadata fields
        if apply_block.metadata.bitcoin_anchor_block_identifier:
            metadata_dict["bitcoin_anchor_block_identifier"] = {
                "hash": apply_block.metadata.bitcoin_anchor_block_identifier.hash,
                "index": apply_block.metadata.bitcoin_anchor_block_identifier.index,
            }

        # Add optional metadata fields if they exist
        optional_fields = [
            "pox_cycle_index",
            "pox_cycle_length",
            "pox_cycle_position",
            "cycle_number",
            "signer_bitvec",
            "signer_public_keys",
            "signer_signature",
            "tenure_height",
            "confirm_microblock_identifier",
            "reward_set",
        ]

        for field in optional_fields:
            value = getattr(apply_block.metadata, field, None)
            if value is not None:
                metadata_dict[field] = value

        return {
            "apply": [
                {
                    "block_identifier": {
                        "hash": apply_block.block_identifier.hash,
                        "index": apply_block.block_identifier.index,
                    },
                    "metadata": metadata_dict,
                    "parent_block_identifier": {
                        "hash": apply_block.parent_block_identifier.hash,
                        "index": apply_block.parent_block_identifier.index,
                    },
                    "timestamp": apply_block.timestamp,
                    "transactions": [
                        {
                            "transaction_identifier": {
                                "hash": tx.transaction_identifier.hash
                            },
                            "metadata": tx.metadata,
                            "operations": tx.operations,
                        }
                        for tx in apply_block.transactions
                    ],
                }
            ],
            "chainhook": {
                "is_streaming_blocks": chainhook_info.is_streaming_blocks,
                "predicate": {
                    "scope": chainhook_info.predicate.scope,
                    "higher_than": chainhook_info.predicate.higher_than,
                },
                "uuid": chainhook_info.uuid,
            },
            "events": [],
            "rollback": [],
        }

    def _create_transaction_description(self, tx) -> str:
        """Create a meaningful transaction description based on transaction data.

        Args:
            tx: Transaction data (dict or object)

        Returns:
            str: Human-readable transaction description
        """
        if isinstance(tx, dict):
            tx_type = tx.get("tx_type", "")
            token_transfer = tx.get("token_transfer")
        else:
            tx_type = getattr(tx, "tx_type", "")
            token_transfer = getattr(tx, "token_transfer", None)

        if (
            tx_type in ["token_transfer", "stx_transfer", "NativeTokenTransfer"]
            and token_transfer
        ):
            if isinstance(token_transfer, dict):
                amount = token_transfer.get("amount", "0")
                recipient = token_transfer.get("recipient_address", "")
                sender = (
                    tx.get("sender_address", "")
                    if isinstance(tx, dict)
                    else getattr(tx, "sender_address", "")
                )
            else:
                amount = getattr(token_transfer, "amount", "0")
                recipient = getattr(token_transfer, "recipient_address", "")
                sender = (
                    tx.get("sender_address", "")
                    if isinstance(tx, dict)
                    else getattr(tx, "sender_address", "")
                )

            return f"transfered: {amount} µSTX from {sender} to {recipient}"
        elif tx_type == "coinbase":
            return "coinbase transaction"
        elif tx_type == "contract_call":
            if isinstance(tx, dict):
                contract_call = tx.get("contract_call", {})
                if isinstance(contract_call, dict):
                    contract_id = contract_call.get("contract_id", "")
                    function_name = contract_call.get("function_name", "")
                    return f"contract call: {contract_id}::{function_name}"
            else:
                contract_call = getattr(tx, "contract_call", None)
                if contract_call:
                    contract_id = getattr(contract_call, "contract_id", "")
                    function_name = getattr(contract_call, "function_name", "")
                    return f"contract call: {contract_id}::{function_name}"

        # Fallback description
        tx_id = (
            tx.get("tx_id", "") if isinstance(tx, dict) else getattr(tx, "tx_id", "")
        )
        return f"Transaction {tx_id}"

    def _create_transaction_operations(
        self, tx, token_transfer=None
    ) -> List[Dict[str, Any]]:
        """Create transaction operations based on transaction type and data.

        Args:
            tx: Transaction data (dict or object)
            token_transfer: Token transfer data if available

        Returns:
            List[Dict[str, Any]]: List of operations for the transaction
        """
        operations = []

        if isinstance(tx, dict):
            tx_type = tx.get("tx_type", "")
            sender_address = tx.get("sender_address", "")
        else:
            tx_type = getattr(tx, "tx_type", "")
            sender_address = getattr(tx, "sender_address", "")

        # Handle token transfers
        if (
            tx_type in ["token_transfer", "stx_transfer", "NativeTokenTransfer"]
            and token_transfer
        ):
            if isinstance(token_transfer, dict):
                amount = int(token_transfer.get("amount", "0"))
                recipient = token_transfer.get("recipient_address", "")
            else:
                amount = int(getattr(token_transfer, "amount", "0"))
                recipient = getattr(token_transfer, "recipient_address", "")

            # Debit operation (sender)
            operations.append(
                {
                    "account": {"address": sender_address},
                    "amount": {
                        "currency": {"decimals": 6, "symbol": "STX"},
                        "value": amount,
                    },
                    "operation_identifier": {"index": 0},
                    "related_operations": [{"index": 1}],
                    "status": "SUCCESS",
                    "type": "DEBIT",
                }
            )

            # Credit operation (recipient)
            operations.append(
                {
                    "account": {"address": recipient},
                    "amount": {
                        "currency": {"decimals": 6, "symbol": "STX"},
                        "value": amount,
                    },
                    "operation_identifier": {"index": 1},
                    "related_operations": [{"index": 0}],
                    "status": "SUCCESS",
                    "type": "CREDIT",
                }
            )

        return operations

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, blockchain RPC issues
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on configuration errors
        if "not configured" in str(error).lower():
            return False
        if "invalid contract" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[ChainStateMonitorResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "rpc" in str(error).lower():
            logger.warning(f"Blockchain/RPC error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For configuration errors, don't retry
        return [
            ChainStateMonitorResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[ChainStateMonitorResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("Chain state monitor task cleanup completed")

    async def _execute_impl(self, context: JobContext) -> List[ChainStateMonitorResult]:
        """Execute chain state monitoring task with blockchain synchronization."""
        # Use the configured network
        network = config.network.network

        try:
            results = []

            # Get the latest chain state for this network
            latest_chain_state = backend.get_latest_chain_state(network)

            if not latest_chain_state:
                logger.warning(f"No chain state found for network {network}")
                results.append(
                    ChainStateMonitorResult(
                        success=False,
                        message=f"No chain state found for network {network}",
                        network=network,
                        is_stale=True,
                    )
                )
                return results

            # Calculate how old the chain state is
            now = datetime.now()
            last_updated = latest_chain_state.updated_at

            # Convert last_updated to naive datetime if it has timezone info
            if last_updated.tzinfo is not None:
                last_updated = last_updated.replace(tzinfo=None)

            time_difference = now - last_updated
            minutes_difference = time_difference.total_seconds() / 60

            # Get current chain height from API
            try:
                logger.debug("Fetching current chain info from API")
                api_info = self.hiro_api.get_info()

                # Handle different response types
                if isinstance(api_info, dict):
                    # Try to access chain_tip from dictionary
                    if "chain_tip" in api_info:
                        chain_tip = api_info["chain_tip"]
                        current_api_block_height = chain_tip.get("block_height", 0)
                    else:
                        logger.error(f"Missing chain_tip in API response: {api_info}")
                        raise ValueError(
                            "Invalid API response format - missing chain_tip"
                        )
                else:
                    # We have a HiroApiInfo object but chain_tip is still a dict
                    # Access it as a dictionary
                    if isinstance(api_info.chain_tip, dict):
                        current_api_block_height = api_info.chain_tip.get(
                            "block_height", 0
                        )
                    else:
                        current_api_block_height = api_info.chain_tip.block_height

                logger.info(f"Current API block height: {current_api_block_height}")
                db_block_height = latest_chain_state.block_height
                logger.info(f"Current DB block height: {db_block_height}")

                blocks_behind = current_api_block_height - db_block_height

                # Consider stale if more than 10 blocks behind
                stale_threshold_blocks = 10
                is_stale = blocks_behind > stale_threshold_blocks

                logger.info(
                    f"Chain state is {blocks_behind} blocks behind the current chain tip. "
                    f"DB height: {db_block_height}, API height: {current_api_block_height}"
                )

                # Process missing blocks if we're behind
                if blocks_behind > 0 and is_stale:
                    logger.warning(
                        f"Chain state is {blocks_behind} blocks behind, which exceeds the threshold of {stale_threshold_blocks}. "
                        f"DB height: {db_block_height}, API height: {current_api_block_height}"
                    )

                    blocks_processed = []

                    # Process each missing block
                    for height in range(
                        db_block_height + 1, current_api_block_height + 1
                    ):
                        logger.info(
                            f"Processing transactions for block height {height}"
                        )

                        try:
                            # Get all transactions for this block
                            transactions = self.hiro_api.get_all_transactions_by_block(
                                height
                            )

                            # Log transaction count and details
                            logger.info(
                                f"Block {height}: Found {transactions.total} transactions"
                            )

                            # Get block details and burn block height
                            burn_block_height = None
                            if transactions.results:
                                # Handle transactions.results as either dict or object
                                tx = transactions.results[0]
                                if isinstance(tx, dict):
                                    block_hash = tx.get("block_hash")
                                    parent_hash = tx.get("parent_block_hash")
                                    burn_block_height = tx.get("burn_block_height")
                                else:
                                    block_hash = tx.block_hash
                                    parent_hash = tx.parent_block_hash
                                    burn_block_height = getattr(
                                        tx, "burn_block_height", None
                                    )
                            else:
                                # If no transactions, fetch the block directly
                                try:
                                    block = self.hiro_api.get_block_by_height(height)

                                    # Handle different response formats
                                    if isinstance(block, dict):
                                        block_hash = block.get("hash")
                                        parent_hash = block.get("parent_block_hash")
                                        burn_block_height = block.get(
                                            "burn_block_height"
                                        )
                                    else:
                                        block_hash = block.hash
                                        parent_hash = block.parent_block_hash
                                        burn_block_height = getattr(
                                            block, "burn_block_height", None
                                        )

                                    if not block_hash or not parent_hash:
                                        raise ValueError(
                                            f"Missing hash or parent_hash in block data: {block}"
                                        )
                                except Exception as e:
                                    logger.error(
                                        f"Error fetching block {height}: {str(e)}"
                                    )
                                    raise

                            logger.debug(
                                f"Block {height}: burn_block_height={burn_block_height}"
                            )

                            # Convert to chainhook format
                            chainhook_data = self._convert_to_chainhook_format(
                                height,
                                block_hash,
                                parent_hash,
                                transactions,
                                burn_block_height,
                            )

                            # Process through chainhook service
                            result = await self.chainhook_service.process(
                                chainhook_data
                            )
                            logger.info(
                                f"Block {height} processed with result: {result}"
                            )

                            blocks_processed.append(height)

                        except Exception as e:
                            logger.error(
                                f"Error processing block {height}: {str(e)}",
                                exc_info=True,
                            )
                            # Continue with next block instead of failing the entire process

                    results.append(
                        ChainStateMonitorResult(
                            success=True,
                            message=f"Chain state is {blocks_behind} blocks behind. Processed {len(blocks_processed)} blocks.",
                            network=network,
                            is_stale=is_stale,
                            last_updated=last_updated,
                            elapsed_minutes=minutes_difference,
                            blocks_behind=blocks_behind,
                            blocks_processed=blocks_processed,
                        )
                    )
                    return results
                else:
                    logger.info(
                        f"Chain state for network {network} is {'stale' if is_stale else 'fresh'}. "
                        f"{blocks_behind} blocks behind (threshold: {stale_threshold_blocks})."
                    )

                # Return result based on blocks_behind check
                results.append(
                    ChainStateMonitorResult(
                        success=True,
                        message=f"Chain state for network {network} is {blocks_behind} blocks behind",
                        network=network,
                        is_stale=is_stale,
                        last_updated=last_updated,
                        elapsed_minutes=minutes_difference,
                        blocks_behind=blocks_behind,
                    )
                )

                return results

            except Exception as e:
                logger.error(
                    f"Error getting current chain info: {str(e)}", exc_info=True
                )
                # Fall back to legacy time-based staleness check if API call fails
                logger.warning("Falling back to time-based staleness check")
                stale_threshold_minutes = 5
                is_stale = minutes_difference > stale_threshold_minutes

                results.append(
                    ChainStateMonitorResult(
                        success=False,
                        message=f"Error checking chain height, using time-based check instead: {str(e)}",
                        network=network,
                        is_stale=is_stale,
                        last_updated=last_updated,
                        elapsed_minutes=minutes_difference,
                    )
                )
                return results

        except Exception as e:
            logger.error(
                f"Error executing chain state monitoring task: {str(e)}", exc_info=True
            )
            return [
                ChainStateMonitorResult(
                    success=False,
                    message=f"Error executing chain state monitoring task: {str(e)}",
                    network=network,
                    is_stale=True,
                )
            ]


# Create instance for auto-registration
chain_state_monitor = ChainStateMonitorTask()
