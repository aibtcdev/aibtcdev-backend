"""Chain state monitoring task implementation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.backend.factory import backend
from app.config import config as main_config
from app.services.integrations.hiro.hiro_api import HiroApi
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.services.integrations.webhooks.chainhook import ChainhookService
from app.services.processing.stacks_chainhook_adapter import (
    StacksChainhookAdapter,
    AdapterConfig,
    BlockNotFoundError,
    TransformationError,
)

logger = configure_logger(__name__)


@dataclass
class ChainStateMonitorResult(RunnerResult):
    """Result of chain state monitoring operation."""

    network: str = None
    is_stale: bool = False
    last_updated: Optional[datetime] = None
    blocks_behind: int = 0
    blocks_processed: Optional[List[int]] = None

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.network is None:
            self.network = main_config.network.network
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

        # Initialize the Stacks Chainhook Adapter
        adapter_config = AdapterConfig(
            network=main_config.network.network,
            enable_caching=True,
            cache_ttl=300,  # 5 minute cache
            max_concurrent_requests=3,
            enable_hex_decoding=True,
        )
        self.chainhook_adapter = StacksChainhookAdapter(adapter_config)

    def __del__(self):
        """Cleanup when task instance is destroyed."""
        # Note: __del__ can't be async, so we just log if resources weren't properly closed
        if hasattr(self, "chainhook_adapter") and self.chainhook_adapter:
            logger.warning(
                "ChainStateMonitorTask destroyed with open chainhook adapter. "
                "Consider calling close_adapter() explicitly.",
                extra={"task": "chain_state_monitor"},
            )

        if (
            hasattr(self, "hiro_api")
            and self.hiro_api
            and hasattr(self.hiro_api, "_session")
            and self.hiro_api._session
        ):
            logger.warning(
                "ChainStateMonitorTask destroyed with open HiroApi session. "
                "Consider calling close_hiro_api() explicitly.",
                extra={"task": "chain_state_monitor"},
            )

    async def close_adapter(self):
        """Explicitly close the chainhook adapter and cleanup resources."""
        if hasattr(self, "chainhook_adapter") and self.chainhook_adapter:
            try:
                await self.chainhook_adapter.close()
                logger.debug(
                    "Chainhook adapter closed successfully",
                    extra={"task": "chain_state_monitor"},
                )
                self.chainhook_adapter = None
            except Exception as e:
                logger.warning(
                    "Error closing chainhook adapter",
                    extra={"task": "chain_state_monitor", "error": str(e)},
                )

    async def close_hiro_api(self):
        """Explicitly close the HiroApi session and cleanup resources."""
        if hasattr(self, "hiro_api") and self.hiro_api:
            try:
                await self.hiro_api.close()
                logger.debug(
                    "HiroApi session closed successfully",
                    extra={"task": "chain_state_monitor"},
                )
            except Exception as e:
                logger.warning(
                    "Error closing HiroApi session",
                    extra={"task": "chain_state_monitor", "error": str(e)},
                )

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Chain state monitor doesn't require wallet configuration
            # It only reads from the blockchain, no transactions needed
            return True
        except Exception as e:
            logger.error(
                "Error validating chain state monitor config",
                extra={"task": "chain_state_monitor", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for blockchain monitoring."""
        try:
            # Test HiroApi initialization and connectivity using context manager
            async with HiroApi() as hiro_api:
                api_info = await hiro_api.aget_info()
                if not api_info:
                    logger.error(
                        "Cannot connect to Hiro API",
                        extra={"task": "chain_state_monitor"},
                    )
                    return False

                return True
        except Exception as e:
            logger.error(
                "Resource validation failed",
                extra={"task": "chain_state_monitor", "error": str(e)},
            )
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Always valid to run - we want to check chain state freshness
            # even when there's no new data
            return True
        except Exception as e:
            logger.error(
                "Error validating chain state monitor task",
                extra={"task": "chain_state_monitor", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _ensure_adapter_ready(self):
        """Ensure the chainhook adapter is ready for use."""
        if not hasattr(self, "chainhook_adapter") or self.chainhook_adapter is None:
            # Recreate adapter if it's missing
            adapter_config = AdapterConfig(
                network=main_config.network.network,
                enable_caching=True,
                cache_ttl=300,  # 5 minute cache
                max_concurrent_requests=3,
                enable_hex_decoding=True,
            )
            self.chainhook_adapter = StacksChainhookAdapter(adapter_config)
            logger.info(
                "Recreated chainhook adapter",
                extra={"task": "chain_state_monitor"},
            )

    async def _convert_to_chainhook_format(self, block_height: int) -> Dict[str, Any]:
        """Convert block to chainhook format using the Stacks Chainhook Adapter.

        Args:
            block_height: Height of the block to convert

        Returns:
            Dict formatted as a chainhook webhook payload (simulates webhook input)

        Raises:
            TransformationError: If block transformation fails
            BlockNotFoundError: If block is not found
        """
        try:
            logger.debug(
                "Converting block to chainhook format using adapter",
                extra={
                    "task": "chain_state_monitor",
                    "block_height": block_height,
                },
            )

            # Ensure adapter is ready
            await self._ensure_adapter_ready()

            # Use the adapter to get chainhook data for the block (already template-formatted)
            result = await self.chainhook_adapter.get_block_chainhook(
                block_height, use_template=True
            )

            logger.debug(
                "Successfully retrieved template-formatted chainhook data",
                extra={
                    "task": "chain_state_monitor",
                    "block_height": block_height,
                    "transaction_count": len(
                        result.get("apply", [{}])[0].get("transactions", [])
                    ),
                },
            )

            return result

        except BlockNotFoundError as e:
            logger.error(
                "Block not found during chainhook conversion",
                extra={
                    "task": "chain_state_monitor",
                    "block_height": block_height,
                    "error": str(e),
                },
            )
            raise

        except TransformationError as e:
            logger.error(
                "Transformation error during chainhook conversion",
                extra={
                    "task": "chain_state_monitor",
                    "block_height": block_height,
                    "error": str(e),
                    "transformation_stage": getattr(
                        e, "transformation_stage", "unknown"
                    ),
                },
            )
            raise

        except Exception as e:
            error_msg = str(e)

            # Check if this is a "client has been closed" error and try to recover
            if "client has been closed" in error_msg.lower():
                logger.warning(
                    "HTTP client was closed, attempting to recreate adapter",
                    extra={
                        "task": "chain_state_monitor",
                        "block_height": block_height,
                        "error": error_msg,
                    },
                )

                # Try to recreate the adapter and retry once
                try:
                    await self.close_adapter()  # Clean up the old one
                    await self._ensure_adapter_ready()  # Create a new one
                    result = await self.chainhook_adapter.get_block_chainhook(
                        block_height, use_template=True
                    )

                    logger.info(
                        "Successfully recovered from closed client error",
                        extra={
                            "task": "chain_state_monitor",
                            "block_height": block_height,
                        },
                    )

                    return result

                except Exception as retry_error:
                    logger.error(
                        "Failed to recover from closed client error",
                        extra={
                            "task": "chain_state_monitor",
                            "block_height": block_height,
                            "retry_error": str(retry_error),
                        },
                    )
                    raise TransformationError(
                        f"Failed to convert block {block_height} after client recovery: {retry_error}",
                        transformation_stage="client_recovery",
                    ) from retry_error

            logger.error(
                "Unexpected error during chainhook conversion",
                extra={
                    "task": "chain_state_monitor",
                    "block_height": block_height,
                    "error": error_msg,
                },
                exc_info=True,
            )
            raise TransformationError(
                f"Failed to convert block {block_height} to chainhook format: {e}",
                transformation_stage="block_conversion",
            ) from e

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, blockchain RPC issues, and client closed errors
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        error_msg = str(error).lower()

        # Don't retry on configuration errors
        if "not configured" in error_msg:
            return False
        if "invalid contract" in error_msg:
            return False

        # Retry on client closed errors (we handle recovery)
        if "client has been closed" in error_msg:
            return True

        # Retry on transformation errors from client issues
        if isinstance(error, TransformationError) and "client_recovery" in getattr(
            error, "transformation_stage", ""
        ):
            return True

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[ChainStateMonitorResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "rpc" in str(error).lower():
            logger.warning(
                "Blockchain/RPC error, will retry",
                extra={"task": "chain_state_monitor", "error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error, will retry",
                extra={"task": "chain_state_monitor", "error": str(error)},
            )
            return None

        # For configuration errors, don't retry
        return [
            ChainStateMonitorResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def close_all_resources(self):
        """Close all resources (adapter and hiro api) and cleanup."""
        await self.close_adapter()
        await self.close_hiro_api()
        logger.debug(
            "All ChainStateMonitorTask resources closed",
            extra={"task": "chain_state_monitor"},
        )

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[ChainStateMonitorResult]
    ) -> None:
        """Cleanup after task execution."""
        # Close any open HiroApi sessions after execution to prevent resource leaks
        # but keep the chainhook_adapter open for reuse across executions
        await self.close_hiro_api()

        logger.debug(
            "Chain state monitor task cleanup completed",
            extra={"task": "chain_state_monitor"},
        )

    async def _execute_impl(self, context: JobContext) -> List[ChainStateMonitorResult]:
        """Execute chain state monitoring task with blockchain synchronization."""
        # Use the configured network
        network = main_config.network.network

        try:
            results = []

            # Get the latest chain state for this network
            latest_chain_state = backend.get_latest_chain_state(network)

            if not latest_chain_state:
                logger.warning(
                    "No chain state found for network",
                    extra={"task": "chain_state_monitor", "network": network},
                )
                results.append(
                    ChainStateMonitorResult(
                        success=False,
                        message=f"No chain state found for network {network}",
                        network=network,
                        is_stale=True,
                    )
                )
                return results

            # Get the last updated time for logging purposes only
            last_updated = latest_chain_state.updated_at

            # Get current chain height from API
            try:
                logger.debug(
                    "Fetching current chain info from API",
                    extra={"task": "chain_state_monitor"},
                )
                api_info = self.hiro_api.get_info()

                # Handle different response types
                if isinstance(api_info, dict):
                    # Try to access chain_tip from dictionary
                    if "chain_tip" in api_info:
                        chain_tip = api_info["chain_tip"]
                        current_api_block_height = chain_tip.get("block_height", 0)
                    else:
                        logger.error(
                            "Missing chain_tip in API response",
                            extra={
                                "task": "chain_state_monitor",
                                "api_response": api_info,
                            },
                        )
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

                logger.debug(
                    "Current API block height",
                    extra={
                        "task": "chain_state_monitor",
                        "api_block_height": current_api_block_height,
                    },
                )
                db_block_height = latest_chain_state.block_height
                logger.debug(
                    "Current DB block height",
                    extra={
                        "task": "chain_state_monitor",
                        "db_block_height": db_block_height,
                    },
                )

                blocks_behind = current_api_block_height - db_block_height

                # Consider stale if more than 5 blocks behind
                stale_threshold_blocks = 5
                is_stale = blocks_behind > stale_threshold_blocks

                logger.info(
                    f"Chain state {blocks_behind} blocks behind current chain tip",
                    extra={
                        "task": "chain_state_monitor",
                        "db_block_height": db_block_height,
                        "api_block_height": current_api_block_height,
                    },
                )

                # Process missing blocks if we're behind and stale
                if blocks_behind > 0 and is_stale:
                    logger.warning(
                        "Chain state behind and exceeds threshold, processing missing blocks",
                        extra={
                            "task": "chain_state_monitor",
                            "blocks_behind": blocks_behind,
                            "threshold": stale_threshold_blocks,
                            "db_block_height": db_block_height,
                            "api_block_height": current_api_block_height,
                        },
                    )

                    blocks_processed = []

                    # Process each missing block
                    for height in range(
                        db_block_height + 1, current_api_block_height + 1
                    ):
                        logger.info(
                            "Processing transactions for block height",
                            extra={
                                "task": "chain_state_monitor",
                                "block_height": height,
                            },
                        )

                        try:
                            # Convert block to chainhook format using the adapter
                            chainhook_data = await self._convert_to_chainhook_format(
                                height
                            )

                            logger.info(
                                "Generated chainhook message for block processing",
                                extra={
                                    "task": "chain_state_monitor",
                                    "block_height": height,
                                    "transaction_count": len(
                                        chainhook_data.get("apply", [{}])[0].get(
                                            "transactions", []
                                        )
                                    ),
                                    "chainhook_uuid": chainhook_data.get(
                                        "chainhook", {}
                                    ).get("uuid"),
                                },
                            )

                            # Process through chainhook service (simulates full webhook flow: parse + handle)
                            result = await self.chainhook_service.process(
                                chainhook_data
                            )
                            logger.info(
                                "Block processed with result",
                                extra={
                                    "task": "chain_state_monitor",
                                    "block_height": height,
                                    "result": result,
                                },
                            )

                            blocks_processed.append(height)

                        except Exception as e:
                            logger.error(
                                "Error processing block",
                                extra={
                                    "task": "chain_state_monitor",
                                    "block_height": height,
                                    "error": str(e),
                                },
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
                            blocks_behind=blocks_behind,
                            blocks_processed=blocks_processed,
                        )
                    )
                    return results
                else:
                    logger.info(
                        "Chain state status for network",
                        extra={
                            "task": "chain_state_monitor",
                            "network": network,
                            "status": "stale" if is_stale else "fresh",
                            "blocks_behind": blocks_behind,
                            "threshold": stale_threshold_blocks,
                        },
                    )

                # Return result based on blocks_behind check
                results.append(
                    ChainStateMonitorResult(
                        success=True,
                        message=f"Chain state for network {network} is {blocks_behind} blocks behind",
                        network=network,
                        is_stale=is_stale,
                        last_updated=last_updated,
                        blocks_behind=blocks_behind,
                    )
                )

                return results

            except Exception as e:
                logger.error(
                    "Error getting current chain info",
                    extra={"task": "chain_state_monitor", "error": str(e)},
                    exc_info=True,
                )
                # Cannot determine staleness without API access
                logger.warning(
                    "Cannot determine chain state without API access",
                    extra={"task": "chain_state_monitor"},
                )

                results.append(
                    ChainStateMonitorResult(
                        success=False,
                        message=f"Error checking chain height: {str(e)}",
                        network=network,
                        is_stale=True,  # Assume stale if we can't check
                        last_updated=last_updated,
                    )
                )
                return results

        except Exception as e:
            logger.error(
                "Error executing chain state monitoring task",
                extra={"task": "chain_state_monitor", "error": str(e)},
                exc_info=True,
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
