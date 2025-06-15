"""DAO token holders monitoring task implementation."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from backend.factory import backend
from backend.models import (
    HolderBase,
    HolderCreate,
    HolderFilter,
    WalletFilter,
)
from lib.hiro import HiroApi
from lib.logger import configure_logger
from services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from services.infrastructure.job_management.decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class DaoTokenHoldersMonitorResult(RunnerResult):
    """Result of DAO token holders monitoring operation."""

    tokens_processed: int = 0
    holders_created: int = 0
    holders_updated: int = 0
    holders_removed: int = 0
    errors: List[str] = None

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.errors is None:
            self.errors = []


@job(
    job_type="dao_token_holders_monitor",
    name="DAO Token Holders Monitor",
    description="Monitors and syncs DAO token holders with blockchain data every 5 minutes",
    interval_seconds=300,  # 5 minutes
    priority=JobPriority.MEDIUM,
    max_retries=3,
    retry_delay_seconds=120,
    timeout_seconds=600,  # 10 minutes timeout
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=10,
    enable_dead_letter_queue=True,
)
class DaoTokenHoldersMonitorTask(BaseTask[DaoTokenHoldersMonitorResult]):
    """Task for monitoring and syncing DAO token holders with blockchain data."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self.hiro_api = HiroApi()

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Token holders monitor doesn't require wallet configuration
            # It only reads from the blockchain and updates database
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO token holders monitor config: {str(e)}",
                exc_info=True,
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
            # Always valid to run - we want to keep holders data fresh
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO token holders monitor task: {str(e)}",
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
        if "invalid token" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DaoTokenHoldersMonitorResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "rpc" in str(error).lower():
            logger.warning(f"Blockchain/RPC error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For configuration errors, don't retry
        return [
            DaoTokenHoldersMonitorResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DaoTokenHoldersMonitorResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("DAO token holders monitor task cleanup completed")

    def _parse_token_identifier(self, token) -> Optional[str]:
        """Parse token identifier for Hiro API call."""
        if hasattr(token, "contract_principal") and token.contract_principal:
            return token.contract_principal
        elif hasattr(token, "symbol") and token.symbol:
            return token.symbol
        elif hasattr(token, "name") and token.name:
            return token.name
        else:
            logger.warning(f"Could not determine token identifier for token {token.id}")
            return None

    def _get_wallet_for_address(self, address: str):
        """Get existing wallet for a given address. Returns None if no wallet exists."""
        try:
            # Try to find existing wallet by address
            mainnet_wallets = backend.list_wallets(
                filters=WalletFilter(mainnet_address=address)
            )
            if mainnet_wallets:
                return mainnet_wallets[0]

            testnet_wallets = backend.list_wallets(
                filters=WalletFilter(testnet_address=address)
            )
            if testnet_wallets:
                return testnet_wallets[0]

            # If no wallet found, return None (don't create new wallet)
            logger.debug(f"No existing wallet found for address {address}")
            return None

        except Exception as e:
            logger.error(f"Error getting wallet for address {address}: {str(e)}")
            return None

    async def _sync_token_holders(
        self, token, result: DaoTokenHoldersMonitorResult
    ) -> None:
        """Sync holders for a specific token."""
        try:
            token_identifier = self._parse_token_identifier(token)
            if not token_identifier:
                error_msg = f"Could not parse token identifier for token {token.id}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                return

            logger.info(f"Syncing holders for token {token.name} ({token_identifier})")

            # Get all current holders from Hiro API (with pagination)
            try:
                api_holders_response = self.hiro_api.get_all_token_holders(
                    token_identifier
                )
                logger.debug(
                    f"API response for token {token_identifier}: {api_holders_response}"
                )
            except Exception as e:
                error_msg = f"Error fetching holders from API for token {token_identifier}: {str(e)}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                return

            # Parse API response
            api_holders = []
            if (
                isinstance(api_holders_response, dict)
                and "results" in api_holders_response
            ):
                api_holders = api_holders_response["results"]
            elif isinstance(api_holders_response, list):
                api_holders = api_holders_response
            else:
                logger.warning(
                    f"Unexpected API response format for token {token_identifier}"
                )
                return

            logger.info(
                f"Found {len(api_holders)} holders from API for token {token.name}"
            )

            # Get current holders from database
            db_holders = backend.list_holders(HolderFilter(token_id=token.id))
            logger.info(
                f"Found {len(db_holders)} existing holders in database for token {token.name}"
            )

            # Create lookup maps
            db_holders_by_wallet = {holder.wallet_id: holder for holder in db_holders}
            api_holders_by_address = {}

            # Process API holders
            for api_holder in api_holders:
                try:
                    # Parse holder data from Hiro API response format
                    address = api_holder.get("address")
                    balance = api_holder.get("balance", "0")

                    if not address:
                        logger.warning(
                            f"No address found in API holder data: {api_holder}"
                        )
                        continue

                    if not balance:
                        logger.warning(
                            f"No balance found for address {address}, defaulting to 0"
                        )
                        balance = "0"

                    api_holders_by_address[address] = balance

                    # Get existing wallet for this address
                    wallet = self._get_wallet_for_address(address)
                    if not wallet:
                        logger.debug(
                            f"No existing wallet found for address {address}, skipping holder record"
                        )
                        continue

                    # Check if we already have this holder in the database
                    if wallet.id in db_holders_by_wallet:
                        # Update existing holder
                        existing_holder = db_holders_by_wallet[wallet.id]
                        if existing_holder.amount != str(balance):
                            logger.info(
                                f"Updating holder {address}: {existing_holder.amount} -> {balance}"
                            )
                            update_data = HolderBase(
                                amount=str(balance), updated_at=datetime.now()
                            )
                            backend.update_holder(existing_holder.id, update_data)
                            result.holders_updated += 1
                    else:
                        # Create new holder
                        logger.info(
                            f"Creating new holder {address} with balance {balance}"
                        )
                        holder_create = HolderCreate(
                            wallet_id=wallet.id,
                            token_id=token.id,
                            dao_id=token.dao_id,
                            amount=str(balance),
                            updated_at=datetime.now(),
                        )
                        backend.create_holder(holder_create)
                        result.holders_created += 1

                except Exception as e:
                    error_msg = f"Error processing API holder {api_holder}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            # Check for holders that are no longer in the API response (removed holders)
            for db_holder in db_holders:
                wallet = backend.get_wallet(db_holder.wallet_id)
                if wallet:
                    address = wallet.mainnet_address or wallet.testnet_address
                    if address and address not in api_holders_by_address:
                        # This holder is no longer holding tokens, remove from database
                        logger.info(
                            f"Removing holder {address} (no longer holds tokens)"
                        )
                        backend.delete_holder(db_holder.id)
                        result.holders_removed += 1

        except Exception as e:
            error_msg = f"Error syncing holders for token {token.id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DaoTokenHoldersMonitorResult]:
        """Execute DAO token holders monitoring task."""
        logger.info("Starting DAO token holders monitoring task")

        result = DaoTokenHoldersMonitorResult(
            success=True, message="DAO token holders sync completed"
        )

        try:
            # Get all tokens from the database
            all_tokens = backend.list_tokens()
            logger.info(f"Found {len(all_tokens)} tokens to process")

            if not all_tokens:
                result.message = "No tokens found to process"
                return [result]

            # Process each token
            for token in all_tokens:
                try:
                    logger.info(f"Processing token: {token.name} (ID: {token.id})")
                    await self._sync_token_holders(token, result)
                    result.tokens_processed += 1

                except Exception as e:
                    error_msg = f"Error processing token {token.id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    result.errors.append(error_msg)
                    # Continue processing other tokens even if one fails

            # Update result message with summary
            summary = (
                f"Processed {result.tokens_processed} tokens. "
                f"Created {result.holders_created}, updated {result.holders_updated}, "
                f"removed {result.holders_removed} holders."
            )

            if result.errors:
                summary += f" Encountered {len(result.errors)} errors."
                result.success = False

            result.message = summary
            logger.info(summary)

            return [result]

        except Exception as e:
            error_msg = f"Error executing DAO token holders monitoring task: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return [
                DaoTokenHoldersMonitorResult(
                    success=False, message=error_msg, error=e, errors=[error_msg]
                )
            ]


# Create instance for auto-registration
dao_token_holders_monitor = DaoTokenHoldersMonitorTask()
