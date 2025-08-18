"""Chainhook monitoring task implementation."""

from dataclasses import dataclass
from typing import List, Optional

from app.backend.factory import backend
from app.config import config
from app.services.integrations.hiro.platform_api import PlatformApi
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class ChainhookMonitorResult(RunnerResult):
    """Result of chainhook monitoring operation."""

    network: str = None
    chainhooks_checked: int = 0
    chainhooks_failed: int = 0
    chainhooks_recreated: int = 0
    failed_chainhook_ids: Optional[List[str]] = None
    recreated_chainhook_ids: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.network is None:
            self.network = config.network.network
        if self.failed_chainhook_ids is None:
            self.failed_chainhook_ids = []
        if self.recreated_chainhook_ids is None:
            self.recreated_chainhook_ids = []


@job(
    job_type="chainhook_monitor",
    name="Chainhook Monitor",
    description="Monitors chainhook status and recreates failed chainhooks",
    interval_seconds=300,  # 5 minutes
    priority=JobPriority.MEDIUM,
    max_retries=3,
    retry_delay_seconds=120,
    timeout_seconds=180,
    max_concurrent=1,
    requires_blockchain=True,
    enable_dead_letter_queue=True,
)
class ChainhookMonitorTask(BaseTask[ChainhookMonitorResult]):
    """Task for monitoring chainhook status and recreating failed ones."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self.platform_api = PlatformApi()

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Chainhook monitor doesn't require wallet configuration
            # It only reads chainhook status and creates new ones
            return True
        except Exception as e:
            logger.error(
                f"Error validating chainhook monitor config: {str(e)}", exc_info=True
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for chainhook monitoring."""
        try:
            # Test Platform API connectivity
            platform_api = PlatformApi()
            # Try to list chainhooks to test connectivity
            chainhooks = platform_api.list_chainhooks()
            logger.debug(
                f"Platform API test successful, found {len(chainhooks)} chainhooks"
            )
            return True
        except Exception as e:
            logger.error(f"Resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Always valid to run - we want to check chainhook status regularly
            return True
        except Exception as e:
            logger.error(
                f"Error validating chainhook monitor task: {str(e)}", exc_info=True
            )
            return False

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, API issues
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
    ) -> Optional[List[ChainhookMonitorResult]]:
        """Handle execution errors with recovery logic."""
        if "api" in str(error).lower() or "platform" in str(error).lower():
            logger.warning(f"Platform API error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For configuration errors, don't retry
        return [
            ChainhookMonitorResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[ChainhookMonitorResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("Chainhook monitor task cleanup completed")

    def _is_chainhook_healthy(self, chainhook_uuid: str) -> bool:
        """Check if a chainhook is in a healthy state by checking its status directly.

        Args:
            chainhook_uuid: UUID of the chainhook to check

        Returns:
            bool: True if chainhook is healthy, False otherwise
        """
        try:
            # Get the specific chainhook status
            status_response = self.platform_api.get_chainhook_status(chainhook_uuid)

            # Check if chainhook is enabled
            if not status_response.get("enabled", False):
                logger.warning(f"Chainhook {chainhook_uuid} is not enabled")
                return False

            # Check status type for any failure indicators
            status_info = status_response.get("status", {})
            status_type = status_info.get("type", "").lower()

            if status_type in ["failed", "error", "disabled", "terminated", "expired"]:
                logger.warning(
                    f"Chainhook {chainhook_uuid} has status type: {status_type}"
                )
                return False

            # Additional checks on status info if available
            info = status_info.get("info", {})
            if info:
                # Check if chainhook has expired
                expired_at = info.get("expired_at_block_height")
                last_evaluated = info.get("last_evaluated_block_height")

                if expired_at and last_evaluated and last_evaluated >= expired_at:
                    logger.warning(
                        f"Chainhook {chainhook_uuid} has expired (expired_at: {expired_at}, last_evaluated: {last_evaluated})"
                    )
                    return False

            return True
        except Exception as e:
            logger.error(f"Error checking chainhook {chainhook_uuid} health: {str(e)}")
            return False

    def _recreate_chainhook_for_chain_state(self, chain_state) -> Optional[str]:
        """Recreate a chainhook for a given chain state.

        Args:
            chain_state: ChainState model instance

        Returns:
            Optional[str]: New chainhook UUID if successful, None otherwise
        """
        try:
            logger.info(
                f"Recreating chainhook for chain state {chain_state.id} on network {chain_state.network}"
            )

            # Create a new block height chainhook starting from this chain state
            response = self.platform_api.create_block_height_hook(
                name=f"{chain_state.network}-block-monitor",
                network=chain_state.network,
                webhook=None,  # Use default webhook
                end_block=None,  # Monitor indefinitely
                expire_after_occurrence=None,  # Don't expire
            )

            new_chainhook_uuid = response.get("chainhookUuid")
            if not new_chainhook_uuid:
                logger.error("No UUID returned from chainhook creation")
                return None

            # Update the chain state with the new chainhook UUID
            from app.backend.models import ChainStateBase

            update_data = ChainStateBase(chainhook_uuid=new_chainhook_uuid)
            backend.update_chain_state(chain_state.id, update_data)

            logger.info(
                f"Successfully created new chainhook {new_chainhook_uuid} for chain state {chain_state.id}"
            )
            return new_chainhook_uuid

        except Exception as e:
            logger.error(
                f"Error recreating chainhook for chain state {chain_state.id}: {str(e)}"
            )
            return None

    async def _execute_impl(self, context: JobContext) -> List[ChainhookMonitorResult]:
        """Execute chainhook monitoring task."""
        # Use the configured network
        network = config.network.network

        try:
            results = []
            chainhooks_checked = 0
            chainhooks_failed = 0
            chainhooks_recreated = 0
            failed_chainhook_ids = []
            recreated_chainhook_ids = []

            # Get all chain states for this network
            chain_states = backend.list_chain_states()
            chain_states_for_network = [
                cs for cs in chain_states if cs.network == network
            ]

            # Separate chain states with and without chainhook UUIDs
            chain_states_with_chainhooks = [
                cs for cs in chain_states_for_network if cs.chainhook_uuid is not None
            ]
            chain_states_without_chainhooks = [
                cs for cs in chain_states_for_network if cs.chainhook_uuid is None
            ]

            logger.info(
                f"Found {len(chain_states_with_chainhooks)} chain states with chainhooks and {len(chain_states_without_chainhooks)} without chainhooks for network {network}"
            )

            # First, create chainhooks for chain states that don't have them
            for chain_state in chain_states_without_chainhooks:
                logger.info(
                    f"Creating chainhook for chain state {chain_state.id} without chainhook_uuid"
                )
                new_uuid = self._recreate_chainhook_for_chain_state(chain_state)
                if new_uuid:
                    chainhooks_recreated += 1
                    recreated_chainhook_ids.append(new_uuid)
                    logger.info(
                        f"Successfully created new chainhook {new_uuid} for chain state {chain_state.id}"
                    )
                else:
                    logger.error(
                        f"Failed to create chainhook for chain state {chain_state.id}"
                    )

            # Continue with monitoring existing chainhooks
            if not chain_states_with_chainhooks and not chain_states_without_chainhooks:
                # No chain states to monitor
                results.append(
                    ChainhookMonitorResult(
                        success=True,
                        message=f"No chain states found for network {network}",
                        network=network,
                        chainhooks_checked=0,
                        chainhooks_failed=0,
                        chainhooks_recreated=chainhooks_recreated,
                        recreated_chainhook_ids=recreated_chainhook_ids,
                    )
                )
                return results

            # If we only had chain states without chainhooks and handled them all, we're done
            if not chain_states_with_chainhooks:
                message = f"Created chainhooks for {len(chain_states_without_chainhooks)} chain states without chainhook UUIDs for network {network}."
                results.append(
                    ChainhookMonitorResult(
                        success=True,
                        message=message,
                        network=network,
                        chainhooks_checked=0,
                        chainhooks_failed=0,
                        chainhooks_recreated=chainhooks_recreated,
                        recreated_chainhook_ids=recreated_chainhook_ids,
                    )
                )
                return results

            # Check each chain state's chainhook status directly
            for chain_state in chain_states_with_chainhooks:
                chainhook_uuid = chain_state.chainhook_uuid
                # Since we filtered for non-None chainhook_uuid, this should never be None
                # but add an assertion for type safety
                if chainhook_uuid is None:
                    logger.error(
                        f"Chain state {chain_state.id} has None chainhook_uuid, skipping"
                    )
                    continue

                chainhooks_checked += 1

                logger.debug(
                    f"Checking chainhook {chainhook_uuid} status for chain state {chain_state.id}"
                )

                # Check if chainhook is healthy using direct status check
                if not self._is_chainhook_healthy(chainhook_uuid):
                    logger.warning(
                        f"Chainhook {chainhook_uuid} is unhealthy or not found"
                    )
                    chainhooks_failed += 1
                    failed_chainhook_ids.append(chainhook_uuid)

                    # Try to recreate the chainhook
                    new_uuid = self._recreate_chainhook_for_chain_state(chain_state)
                    if new_uuid:
                        chainhooks_recreated += 1
                        recreated_chainhook_ids.append(new_uuid)
                        logger.info(
                            f"Successfully recreated chainhook {new_uuid} to replace unhealthy {chainhook_uuid}"
                        )

                        # Delete the old chainhook if it exists
                        try:
                            self.platform_api.delete_chainhook(chainhook_uuid)
                            logger.info(f"Deleted old chainhook {chainhook_uuid}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete old chainhook {chainhook_uuid}: {str(e)}"
                            )
                    else:
                        logger.error(
                            f"Failed to recreate chainhook for chain state {chain_state.id}"
                        )
                else:
                    logger.debug(f"Chainhook {chainhook_uuid} is healthy")

            # Create result summary
            message = (
                f"Monitored {chainhooks_checked} chainhooks for network {network}. "
            )
            if chainhooks_failed > 0:
                message += f"Found {chainhooks_failed} failed chainhooks. "
                if chainhooks_recreated > 0:
                    message += (
                        f"Successfully recreated {chainhooks_recreated} chainhooks."
                    )
                else:
                    message += "Failed to recreate any chainhooks."
            else:
                message += "All chainhooks are healthy."

            results.append(
                ChainhookMonitorResult(
                    success=True,
                    message=message,
                    network=network,
                    chainhooks_checked=chainhooks_checked,
                    chainhooks_failed=chainhooks_failed,
                    chainhooks_recreated=chainhooks_recreated,
                    failed_chainhook_ids=failed_chainhook_ids,
                    recreated_chainhook_ids=recreated_chainhook_ids,
                )
            )

            return results

        except Exception as e:
            logger.error(
                f"Error executing chainhook monitoring task: {str(e)}", exc_info=True
            )
            return [
                ChainhookMonitorResult(
                    success=False,
                    message=f"Error executing chainhook monitoring task: {str(e)}",
                    network=network,
                    error=e,
                )
            ]


# Create instance for auto-registration
chainhook_monitor = ChainhookMonitorTask()
