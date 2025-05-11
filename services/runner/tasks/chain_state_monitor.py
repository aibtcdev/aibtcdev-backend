"""Chain state monitoring task implementation."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.factory import backend
from config import config
from lib.hiro import HiroApi
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerResult
from services.webhooks.chainhook import ChainhookService
from services.webhooks.chainhook.models import (
    Apply,
    BlockIdentifier,
    BlockMetadata,
    ChainHookData,
    ChainHookInfo,
    Predicate,
    TransactionIdentifier,
    TransactionMetadata,
    TransactionWithReceipt,
)

logger = configure_logger(__name__)


class ChainStateMonitorResult(RunnerResult):
    """Result of chain state monitoring operation."""

    def __init__(
        self,
        success: bool,
        message: str,
        error: Optional[Exception] = None,
        network: str = None,
        is_stale: bool = False,
        last_updated: Optional[datetime] = None,
        elapsed_minutes: float = 0,
        blocks_behind: int = 0,
        blocks_processed: Optional[List[int]] = None,
    ):
        """Initialize with required and optional parameters.

        Args:
            success: Whether the operation was successful
            message: Message describing the operation result
            error: Optional exception that occurred
            network: The network being monitored (optional, defaults to None)
            is_stale: Whether the chain state is stale (optional, defaults to False)
            last_updated: When the chain state was last updated
            elapsed_minutes: Minutes since last update
            blocks_behind: Number of blocks behind
            blocks_processed: List of blocks processed
        """
        super().__init__(success=success, message=message, error=error)
        self.network = (
            network or config.network.network
        )  # Use config network as default
        self.is_stale = is_stale
        self.last_updated = last_updated
        self.elapsed_minutes = elapsed_minutes
        self.blocks_behind = blocks_behind
        self.blocks_processed = blocks_processed if blocks_processed is not None else []


class ChainStateMonitorTask(BaseTask[ChainStateMonitorResult]):
    """Task runner for monitoring chain state freshness."""

    def __init__(self):
        """Initialize the task without requiring config parameter."""
        # No config parameter needed - we get it from the import
        super().__init__()
        self.hiro_api = HiroApi()
        self.chainhook_service = ChainhookService()

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        # Always valid to run - we want to check chain state freshness
        # even when there's no new data
        return True

    def _convert_to_chainhook_format(
        self, block_height: int, block_hash: str, parent_hash: str, transactions: Any
    ) -> Dict[str, Any]:
        """Convert block transactions to chainhook format.

        Args:
            block_height: Height of the block
            block_hash: Hash of the block
            parent_hash: Hash of the parent block
            transactions: Block transactions from Hiro API

        Returns:
            Dict formatted as a chainhook webhook payload
        """
        # Create block identifier
        block_identifier = BlockIdentifier(hash=block_hash, index=block_height)

        # Create parent block identifier
        parent_block_identifier = BlockIdentifier(
            hash=parent_hash, index=block_height - 1
        )

        # Create basic metadata
        metadata = BlockMetadata(
            block_time=int(datetime.now().timestamp()), stacks_block_hash=block_hash
        )

        # Convert transactions to chainhook format
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
                sponsored = tx.get("sponsored", False)
                tx_status = tx.get("tx_status", "")
                tx_type = tx.get("tx_type", "")
                tx_result_repr = (
                    tx.get("tx_result", {}).get("repr", "")
                    if isinstance(tx.get("tx_result"), dict)
                    else ""
                )
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
                sponsored = tx.sponsored
                tx_status = tx.tx_status
                tx_type = tx.tx_type
                tx_result_repr = (
                    tx.tx_result.repr if hasattr(tx.tx_result, "repr") else ""
                )

            # Create transaction identifier
            tx_identifier = TransactionIdentifier(hash=tx_id)

            # Create transaction metadata
            tx_metadata = {
                "description": f"Transaction {tx_id}",
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
                    else 0
                ),
                "kind": {"type": tx_type},
                "nonce": nonce,
                "position": {"index": tx_index},
                "raw_tx": "",  # We don't have this from the v2 API
                "receipt": {
                    "contract_calls_stack": [],
                    "events": [],
                    "mutated_assets_radius": [],
                    "mutated_contracts_radius": [],
                },
                "result": tx_result_repr,
                "sender": sender_address,
                "sponsor": sponsor_address,
                "success": tx_status == "success",
            }

            # Create transaction with receipt
            tx_with_receipt = TransactionWithReceipt(
                transaction_identifier=tx_identifier,
                metadata=tx_metadata,
                operations=[],
            )

            chainhook_transactions.append(tx_with_receipt)

        # Create apply block
        apply_block = Apply(
            block_identifier=block_identifier,
            parent_block_identifier=parent_block_identifier,
            metadata=metadata,
            timestamp=int(datetime.now().timestamp()),
            transactions=chainhook_transactions,
        )

        # Create predicate
        predicate = Predicate(scope="block_height", higher_than=block_height - 1)

        # Create chainhook info
        chainhook_info = ChainHookInfo(
            is_streaming_blocks=False, predicate=predicate, uuid=str(uuid.uuid4())
        )

        # Create full chainhook data
        chainhook_data = ChainHookData(
            apply=[apply_block], chainhook=chainhook_info, events=[], rollback=[]
        )

        # Convert to dict for webhook processing
        return {
            "apply": [
                {
                    "block_identifier": {
                        "hash": apply_block.block_identifier.hash,
                        "index": apply_block.block_identifier.index,
                    },
                    "metadata": {
                        "block_time": apply_block.metadata.block_time,
                        "stacks_block_hash": apply_block.metadata.stacks_block_hash,
                    },
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
                            "operations": [],
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

    async def _execute_impl(self, context: JobContext) -> List[ChainStateMonitorResult]:
        """Run the chain state monitoring task."""
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
                logger.info("Fetching current chain info from API")
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

                            # Get block details
                            if transactions.results:
                                # Handle transactions.results as either dict or object
                                tx = transactions.results[0]
                                if isinstance(tx, dict):
                                    block_hash = tx.get("block_hash")
                                    parent_hash = tx.get("parent_block_hash")
                                else:
                                    block_hash = tx.block_hash
                                    parent_hash = tx.parent_block_hash
                            else:
                                # If no transactions, fetch the block directly
                                try:
                                    block = self.hiro_api.get_block_by_height(height)

                                    # Handle different response formats
                                    if isinstance(block, dict):
                                        block_hash = block.get("hash")
                                        parent_hash = block.get("parent_block_hash")
                                    else:
                                        block_hash = block.hash
                                        parent_hash = block.parent_block_hash

                                    if not block_hash or not parent_hash:
                                        raise ValueError(
                                            f"Missing hash or parent_hash in block data: {block}"
                                        )
                                except Exception as e:
                                    logger.error(
                                        f"Error fetching block {height}: {str(e)}"
                                    )
                                    raise

                            # Convert to chainhook format
                            chainhook_data = self._convert_to_chainhook_format(
                                height, block_hash, parent_hash, transactions
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


# Instantiate the task for use in the registry
chain_state_monitor = ChainStateMonitorTask()
