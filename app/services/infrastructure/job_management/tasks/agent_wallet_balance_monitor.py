"""Agent wallet balance monitoring task implementation."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.backend.factory import backend
from app.backend.models import (
    WalletBase,
    WalletFilter,
    QueueMessageCreate,
    QueueMessageType,
)
from app.services.integrations.hiro.hiro_api import HiroApi
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.config import config as app_config

logger = configure_logger(__name__)


@dataclass
class AgentWalletBalanceMonitorResult(RunnerResult):
    """Result of agent wallet balance monitoring operation."""

    wallets_processed: int = 0
    wallets_updated: int = 0
    funding_requests_queued: int = 0
    total_balance_checked: str = "0"
    low_balance_wallets: int = 0
    errors: List[str] = None

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.errors is None:
            self.errors = []


@job(
    job_type="agent_wallet_balance_monitor",
    name="Agent Wallet Balance Monitor",
    description="Monitors agent wallet STX balances and auto-funds low balance wallets every 5 minutes",
    interval_seconds=300,  # 5 minutes
    priority=JobPriority.HIGH,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=300,  # 5 minutes timeout
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=20,
    enable_dead_letter_queue=True,
)
class AgentWalletBalanceMonitorTask(BaseTask[AgentWalletBalanceMonitorResult]):
    """Task for monitoring agent wallet STX balances and auto-funding when needed."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self.hiro_api = HiroApi()
        # Configurable funding thresholds using global config
        self.min_balance_threshold = int(
            app_config.stx_transfer_wallet.min_balance_threshold
        )
        self.funding_amount = int(app_config.stx_transfer_wallet.funding_amount)

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if backend wallet is configured for funding
            if not app_config.backend_wallet.seed_phrase:
                logger.error(
                    "Backend wallet seed phrase not configured",
                    extra={
                        "issue": "missing_seed_phrase",
                    },
                )
                return False
            return True
        except Exception as e:
            logger.error(
                "Error validating config",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for blockchain monitoring."""
        return True

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get all agent wallets to check if there are any to process
            agent_wallets = self._get_agent_wallets()
            if not agent_wallets:
                logger.debug(
                    "No agent wallets found to monitor",
                )
                return False

            logger.debug(
                "Found agent wallets to monitor",
                extra={
                    "wallet_count": len(agent_wallets),
                },
            )
            return True
        except Exception as e:
            logger.error(
                "Error validating task",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

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
        if "invalid wallet" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[AgentWalletBalanceMonitorResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "rpc" in str(error).lower():
            logger.warning(
                "Blockchain/RPC error, will retry",
                extra={"error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error, will retry",
                extra={"error": str(error)},
            )
            return None

        # For configuration errors, don't retry
        return [
            AgentWalletBalanceMonitorResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[AgentWalletBalanceMonitorResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("Task cleanup completed")

    def _get_agent_wallets(self) -> List:
        """Get all wallets that have an associated agent."""
        try:
            # Get all agents first
            agents = backend.list_agents()
            if not agents:
                logger.debug("No agents found")
                return []

            # Get wallets for these agents
            agent_ids = [agent.id for agent in agents]
            wallets = []

            for agent_id in agent_ids:
                agent_wallets = backend.list_wallets(
                    filters=WalletFilter(agent_id=agent_id)
                )
                wallets.extend(agent_wallets)

            logger.debug(
                "Found agent wallets",
                extra={"wallet_count": len(wallets)},
            )
            return wallets

        except Exception as e:
            logger.error(
                "Error getting agent wallets",
                extra={"error": str(e)},
            )
            return []

    def _get_wallet_address(self, wallet) -> Optional[str]:
        """Get the appropriate wallet address based on network configuration."""
        # Get network from config
        network = app_config.network.network

        if network == "testnet" and wallet.testnet_address:
            return wallet.testnet_address
        elif wallet.mainnet_address:
            return wallet.mainnet_address
        elif wallet.testnet_address:
            return wallet.testnet_address
        else:
            return None

    async def _get_stx_balance(self, address: str) -> Optional[str]:
        """Get STX balance for a given address."""
        try:
            balance_info = self.hiro_api.get_address_balance(address)
            if balance_info and "stx" in balance_info:
                stx_balance = balance_info["stx"]["balance"]
                logger.debug(
                    "Retrieved STX balance",
                    extra={
                        "address": address,
                        "balance": stx_balance,
                    },
                )
                return str(stx_balance)
            else:
                logger.warning(
                    "No STX balance info found",
                    extra={"address": address},
                )
                return "0"
        except Exception as e:
            logger.error(
                "Error getting STX balance",
                extra={
                    "address": address,
                    "error": str(e),
                },
            )
            return None

    async def _queue_funding_request(
        self, wallet, current_balance: str, reason: str = "Low balance auto-funding"
    ) -> bool:
        """Queue a funding request for the wallet.

        Returns True if funding request was queued successfully, False otherwise.
        """
        try:
            wallet_address = self._get_wallet_address(wallet)
            if not wallet_address:
                logger.warning(
                    "No address found for wallet",
                    extra={"wallet_id": wallet.id},
                )
                return False

            # Create queue message for STX transfer
            funding_message = QueueMessageCreate(
                type=QueueMessageType.get_or_create("stx_transfer"),
                wallet_id=None,  # Use backend wallet for funding
                message={
                    "recipient": wallet_address,
                    "amount": self.funding_amount,
                    "fee": 400,  # Standard fee
                    "memo": f"Auto-fund: {current_balance}",
                    "reason": reason,
                },
            )

            backend.create_queue_message(funding_message)
            logger.info(
                "Queued funding request",
                extra={
                    "wallet_id": wallet.id,
                    "wallet_address": wallet_address,
                    "funding_amount": self.funding_amount,
                    "current_balance": current_balance,
                },
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to queue funding request",
                extra={
                    "wallet_id": wallet.id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return False

    async def _check_wallet_balance(
        self, wallet, result: AgentWalletBalanceMonitorResult
    ) -> None:
        """Check and update balance for a specific wallet."""
        try:
            wallet_address = self._get_wallet_address(wallet)
            if not wallet_address:
                error_msg = f"No address found for wallet {wallet.id}"
                logger.warning(
                    "No address found for wallet",
                    extra={"wallet_id": wallet.id},
                )
                result.errors.append(error_msg)
                return

            logger.debug(
                "Checking wallet balance",
                extra={
                    "wallet_id": wallet.id,
                    "wallet_address": wallet_address,
                },
            )

            # Get current STX balance from blockchain
            current_balance = await self._get_stx_balance(wallet_address)
            if current_balance is None:
                error_msg = f"Could not retrieve balance for wallet {wallet.id} ({wallet_address})"
                logger.error(
                    "Could not retrieve wallet balance",
                    extra={
                        "wallet_id": wallet.id,
                        "wallet_address": wallet_address,
                    },
                )
                result.errors.append(error_msg)
                return

            # Update wallet balance in database
            update_data = WalletBase(
                stx_balance=current_balance,
                balance_updated_at=datetime.now(),
            )

            backend.update_wallet(wallet.id, update_data)
            result.wallets_updated += 1

            logger.info(
                "Updated wallet balance",
                extra={
                    "wallet_id": wallet.id,
                    "balance": current_balance,
                },
            )

            # Check if balance is below threshold and queue funding if needed
            balance_int = int(current_balance)
            if balance_int <= self.min_balance_threshold:
                result.low_balance_wallets += 1
                logger.warning(
                    "Wallet has low balance",
                    extra={
                        "wallet_id": wallet.id,
                        "wallet_address": wallet_address,
                        "current_balance": current_balance,
                        "threshold": self.min_balance_threshold,
                    },
                )

                # Queue funding request
                funding_queued = await self._queue_funding_request(
                    wallet,
                    current_balance,
                    f"Balance {current_balance} below threshold {self.min_balance_threshold}",
                )
                if funding_queued:
                    result.funding_requests_queued += 1

        except Exception as e:
            error_msg = f"Error checking balance for wallet {wallet.id}: {str(e)}"
            logger.error(
                "Error checking wallet balance",
                extra={
                    "wallet_id": wallet.id,
                    "error": str(e),
                },
                exc_info=True,
            )
            result.errors.append(error_msg)

    async def _execute_impl(
        self, context: JobContext
    ) -> List[AgentWalletBalanceMonitorResult]:
        """Execute agent wallet balance monitoring task."""
        logger.info("Starting task")

        result = AgentWalletBalanceMonitorResult(
            success=True, message="Agent wallet balance monitoring completed"
        )

        try:
            # Get all agent wallets
            agent_wallets = self._get_agent_wallets()
            logger.info(
                "Found agent wallets to process",
                extra={
                    "wallet_count": len(agent_wallets),
                },
            )

            if not agent_wallets:
                result.message = "No agent wallets found to process"
                return [result]

            # Process each wallet
            total_balance = 0
            for wallet in agent_wallets:
                try:
                    logger.debug(
                        "Processing wallet",
                        extra={
                            "wallet_id": wallet.id,
                        },
                    )
                    await self._check_wallet_balance(wallet, result)
                    result.wallets_processed += 1

                    # Add to total balance if we have a valid balance
                    if wallet.stx_balance:
                        total_balance += int(wallet.stx_balance)

                except Exception as e:
                    error_msg = f"Error processing wallet {wallet.id}: {str(e)}"
                    logger.error(
                        "Error processing wallet",
                        extra={
                            "wallet_id": wallet.id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                    result.errors.append(error_msg)
                    # Continue processing other wallets even if one fails

            result.total_balance_checked = str(total_balance)

            # Update result message with summary
            summary = (
                f"Processed {result.wallets_processed} wallets. "
                f"Updated {result.wallets_updated} wallet balances. "
                f"Found {result.low_balance_wallets} low balance wallets. "
                f"Queued {result.funding_requests_queued} funding requests. "
                f"Total balance checked: {result.total_balance_checked} microSTX."
            )

            if result.errors:
                summary += f" Encountered {len(result.errors)} errors."
                result.success = False

            result.message = summary
            logger.info(
                "Task completed",
                extra={
                    "wallets_processed": result.wallets_processed,
                    "wallets_updated": result.wallets_updated,
                    "low_balance_wallets": result.low_balance_wallets,
                    "funding_requests_queued": result.funding_requests_queued,
                    "total_balance_checked": result.total_balance_checked,
                    "errors": len(result.errors),
                },
            )

            return [result]

        except Exception as e:
            error_msg = (
                f"Error executing agent wallet balance monitoring task: {str(e)}"
            )
            logger.error(
                "Error executing task",
                extra={"error": str(e)},
                exc_info=True,
            )
            return [
                AgentWalletBalanceMonitorResult(
                    success=False, message=error_msg, error=e, errors=[error_msg]
                )
            ]


# Create instance for auto-registration
agent_wallet_balance_monitor = AgentWalletBalanceMonitorTask()
