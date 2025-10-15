"""DAO token holders monitoring task implementation."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.backend.factory import backend
from app.backend.models import (
    HolderBase,
    HolderCreate,
    HolderFilter,
    AgentFilter,
    WalletFilter,
    ContractStatus,
    ExtensionFilter,
    QueueMessageCreate,
    QueueMessageType,
)
from app.services.integrations.hiro.hiro_api import HiroApi
from app.services.integrations.hiro.utils import HiroApiRateLimitError
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job

import asyncio

logger = configure_logger(__name__)


@dataclass
class DaoTokenHoldersMonitorResult(RunnerResult):
    """Result of DAO token holders monitoring operation."""

    tokens_processed: int = 0
    holders_created: int = 0
    holders_updated: int = 0
    holders_removed: int = 0
    approvals_queued: int = 0
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
                "Error validating DAO token holders monitor config",
                extra={"task": "dao_token_holders_monitor", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for blockchain monitoring."""
        return True

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Always valid to run - we want to keep holders data fresh
            return True
        except Exception as e:
            logger.error(
                "Error validating DAO token holders monitor task",
                extra={"task": "dao_token_holders_monitor", "error": str(e)},
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
            logger.warning(
                "Blockchain/RPC error, will retry",
                extra={"task": "dao_token_holders_monitor", "error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error, will retry",
                extra={"task": "dao_token_holders_monitor", "error": str(error)},
            )
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
        logger.debug(
            "DAO token holders monitor task cleanup completed",
            extra={"task": "dao_token_holders_monitor"},
        )

    async def _parse_token_identifier(self, token) -> Optional[str]:
        """Parse token identifier for Hiro API call.

        Constructs the proper token identifier format: {contract_principal}::{symbol}
        """
        if not hasattr(token, "contract_principal") or not token.contract_principal:
            logger.warning(
                "Token has no contract_principal",
                extra={"task": "dao_token_holders_monitor", "token_id": token.id},
            )
            return None

        contract_principal = token.contract_principal

        try:
            # Get token metadata to extract the symbol
            logger.debug(
                "Fetching metadata for token",
                extra={
                    "task": "dao_token_holders_monitor",
                    "contract_principal": contract_principal,
                },
            )
            metadata = await self.hiro_api.aget_token_metadata(contract_principal)

            # Extract symbol from metadata
            symbol = metadata.get("symbol")
            if not symbol:
                logger.warning(
                    "No symbol found in metadata for token",
                    extra={
                        "task": "dao_token_holders_monitor",
                        "contract_principal": contract_principal,
                    },
                )
                return None

            # Construct the proper token identifier format
            token_identifier = f"{contract_principal}::{symbol}"
            logger.debug(
                "Constructed token identifier",
                extra={
                    "task": "dao_token_holders_monitor",
                    "token_identifier": token_identifier,
                },
            )
            return token_identifier

        except Exception as e:
            logger.error(
                "Error fetching metadata for token",
                extra={
                    "task": "dao_token_holders_monitor",
                    "contract_principal": contract_principal,
                    "error": str(e),
                },
            )
            # Fallback to just the contract principal if metadata fails
            logger.warning(
                "Using contract principal as fallback",
                extra={
                    "task": "dao_token_holders_monitor",
                    "contract_principal": contract_principal,
                },
            )
            return contract_principal

    def _get_agent_for_contract(self, account_contract: str):
        """Get existing agent for a given account_contract. Returns (agent, wallet) tuple if found, None otherwise."""
        try:
            # Try to find existing agent by account_contract
            agents = backend.list_agents(
                filters=AgentFilter(account_contract=account_contract)
            )
            if agents:
                agent = agents[0]
                # Get the wallet for this agent
                wallets = backend.list_wallets(filters=WalletFilter(agent_id=agent.id))
                wallet = wallets[0] if wallets else None
                return agent, wallet

            # If no agent found, return None
            logger.debug(
                "No existing agent found for account_contract",
                extra={
                    "task": "dao_token_holders_monitor",
                    "account_contract": account_contract,
                },
            )
            return None, None

        except Exception as e:
            logger.error(
                "Error getting agent for account_contract",
                extra={
                    "task": "dao_token_holders_monitor",
                    "account_contract": account_contract,
                    "error": str(e),
                },
            )
            return None, None

    async def _queue_proposal_approval_for_agent(
        self,
        agent,
        wallet,
        dao_id,
        token,
        reason: str = "Token holder sync - enabling proposal voting",
    ) -> bool:
        """Queue a proposal approval message for the agent account.

        Returns True if approval was queued successfully, False otherwise.
        """
        try:
            # Check if we have a wallet for this agent
            if not wallet:
                logger.warning(
                    "No wallet found for agent - cannot queue approval",
                    extra={"task": "dao_token_holders_monitor", "agent_id": agent.id},
                )
                return False

            # Find the DAO's ACTION_PROPOSAL_VOTING extension
            extensions = backend.list_extensions(
                ExtensionFilter(
                    dao_id=dao_id,
                    subtype="ACTION_PROPOSAL_VOTING",
                    status=ContractStatus.DEPLOYED,
                )
            )

            if not extensions:
                logger.warning(
                    "No ACTION_PROPOSAL_VOTING extension found for DAO",
                    extra={"task": "dao_token_holders_monitor", "dao_id": dao_id},
                )
                return False

            voting_extension = extensions[0]

            # Create queue message for proposal approval
            approval_message = QueueMessageCreate(
                type=QueueMessageType.get_or_create("agent_account_proposal_approval"),
                dao_id=dao_id,
                wallet_id=wallet.id,  # Include the wallet_id
                message={
                    "agent_account_contract": agent.account_contract,
                    "contract_to_approve": voting_extension.contract_principal,
                    "approval_type": "VOTING",
                    "token_contract": token.contract_principal,
                    "reason": reason,
                },
            )

            backend.create_queue_message(approval_message)
            logger.info(
                "Queued proposal approval for agent",
                extra={
                    "task": "dao_token_holders_monitor",
                    "agent_contract": agent.account_contract,
                    "contract_to_approve": voting_extension.contract_principal,
                    "wallet_id": wallet.id,
                },
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to queue proposal approval for agent",
                extra={
                    "task": "dao_token_holders_monitor",
                    "agent_id": agent.id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return False

    async def _sync_token_holders(
        self, token, result: DaoTokenHoldersMonitorResult
    ) -> None:
        """Sync holders for a specific token."""
        max_retries = 3  # Add per-token retry limit
        for attempt in range(max_retries):
            try:
                token_identifier = await self._parse_token_identifier(token)
                if not token_identifier:
                    error_msg = "Could not parse token identifier for token"
                    logger.error(
                        error_msg,
                        extra={
                            "task": "dao_token_holders_monitor",
                            "token_id": token.id,
                        },
                    )
                    result.errors.append(error_msg)
                    return

                logger.info(
                    "Syncing holders for token",
                    extra={
                        "task": "dao_token_holders_monitor",
                        "token_name": token.name,
                        "token_identifier": token_identifier,
                    },
                )

                # Get all current holders from Hiro API (with pagination)
                api_holders_response = await self.hiro_api.aget_all_token_holders(
                    token_identifier
                )
                logger.debug(
                    "API response for token",
                    extra={
                        "task": "dao_token_holders_monitor",
                        "token_identifier": token_identifier,
                        "response": str(api_holders_response),
                    },
                )

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
                        "Unexpected API response format for token",
                        extra={
                            "task": "dao_token_holders_monitor",
                            "token_identifier": token_identifier,
                        },
                    )
                    return

                logger.info(
                    "Found holders from API for token",
                    extra={
                        "task": "dao_token_holders_monitor",
                        "holder_count": len(api_holders),
                        "token_name": token.name,
                    },
                )

                # Get current holders from database
                db_holders = backend.list_holders(HolderFilter(token_id=token.id))
                logger.info(
                    "Found existing holders in database for token",
                    extra={
                        "task": "dao_token_holders_monitor",
                        "holder_count": len(db_holders),
                        "token_name": token.name,
                    },
                )

                # Create lookup maps by address+token_id (composite key for matching)
                # This allows the same address to hold tokens for multiple DAOs
                db_holders_by_address_token = {
                    (holder.address, holder.token_id): holder for holder in db_holders
                }
                api_holders_by_contract = {}

                # Process API holders
                for api_holder in api_holders:
                    try:
                        # Parse holder data from Hiro API response format
                        address = api_holder.get("address")
                        balance = api_holder.get("balance", "0")

                        if not address:
                            logger.warning(
                                "No address found in API holder data",
                                extra={
                                    "task": "dao_token_holders_monitor",
                                    "api_holder": str(api_holder),
                                },
                            )
                            continue

                        if not balance:
                            logger.warning(
                                "No balance found for address, defaulting to 0",
                                extra={
                                    "task": "dao_token_holders_monitor",
                                    "address": address,
                                },
                            )
                            balance = "0"

                        api_holders_by_contract[address] = balance

                        # Get existing agent and wallet for this account_contract
                        agent, wallet = self._get_agent_for_contract(address)

                        # Check if we already have this holder in the database (by address+token_id)
                        holder_key = (address, token.id)
                        if holder_key in db_holders_by_address_token:
                            # Update existing holder
                            existing_holder = db_holders_by_address_token[holder_key]
                            needs_update = False
                            should_trigger_approval = False

                            update_data = HolderBase(
                                amount=str(balance),
                                updated_at=datetime.now(),
                                address=address,
                            )

                            # Check if we need to update agent_id
                            if agent and existing_holder.agent_id != agent.id:
                                update_data.agent_id = agent.id
                                needs_update = True
                            elif not agent and existing_holder.agent_id is not None:
                                update_data.agent_id = None
                                needs_update = True

                            # Check if we need to update wallet_id
                            if wallet and existing_holder.wallet_id != wallet.id:
                                update_data.wallet_id = wallet.id
                                needs_update = True
                            elif not wallet and existing_holder.wallet_id is not None:
                                update_data.wallet_id = None
                                needs_update = True

                            # Check if amount changed and if this triggers first meaningful balance
                            old_balance = float(existing_holder.amount or "0")
                            new_balance = float(balance)

                            if existing_holder.amount != str(balance):
                                needs_update = True

                                # Check if this is a first meaningful token receipt for an agent
                                if agent and old_balance == 0 and new_balance > 0:
                                    should_trigger_approval = True
                                    logger.info(
                                        "First meaningful token receipt detected for agent during sync - will trigger proposal approval",
                                        extra={
                                            "task": "dao_token_holders_monitor",
                                            "agent_id": agent.id,
                                        },
                                    )

                            # Check if address changed
                            if existing_holder.address != address:
                                needs_update = True

                            if needs_update:
                                logger.info(
                                    "Updating holder for token",
                                    extra={
                                        "task": "dao_token_holders_monitor",
                                        "address": address,
                                        "token_name": token.name,
                                        "amount_old": existing_holder.amount,
                                        "amount_new": balance,
                                        "agent_id_old": existing_holder.agent_id,
                                        "agent_id_new": agent.id if agent else None,
                                        "wallet_id_old": existing_holder.wallet_id,
                                        "wallet_id_new": wallet.id if wallet else None,
                                    },
                                )
                                backend.update_holder(existing_holder.id, update_data)
                                result.holders_updated += 1

                                # Queue proposal approval if this is a first-time meaningful receipt
                                if should_trigger_approval:
                                    approval_queued = (
                                        await self._queue_proposal_approval_for_agent(
                                            agent, wallet, token.dao_id, token
                                        )
                                    )
                                    if approval_queued:
                                        result.approvals_queued += 1
                        else:
                            logger.info(
                                "Creating new holder for token",
                                extra={
                                    "task": "dao_token_holders_monitor",
                                    "address": address,
                                    "token_name": token.name,
                                    "balance": balance,
                                    "agent_id": agent.id if agent else None,
                                    "wallet_id": wallet.id if wallet else None,
                                },
                            )
                            holder_create = HolderCreate(
                                agent_id=agent.id if agent else None,
                                wallet_id=wallet.id if wallet else None,
                                token_id=token.id,
                                dao_id=token.dao_id,
                                amount=str(balance),
                                updated_at=datetime.now(),
                                address=address,
                            )
                            backend.create_holder(holder_create)
                            result.holders_created += 1

                            # Queue proposal approval for new agent holders with positive balance
                            if agent and float(balance) > 0:
                                logger.info(
                                    "First token receipt detected for agent during sync - will trigger proposal approval",
                                    extra={
                                        "task": "dao_token_holders_monitor",
                                        "agent_id": agent.id,
                                    },
                                )
                                approval_queued = (
                                    await self._queue_proposal_approval_for_agent(
                                        agent, wallet, token.dao_id, token
                                    )
                                )
                                if approval_queued:
                                    result.approvals_queued += 1

                    except Exception as e:
                        error_msg = "Error processing API holder"
                        logger.error(
                            error_msg,
                            extra={
                                "task": "dao_token_holders_monitor",
                                "api_holder": str(api_holder),
                                "error": str(e),
                            },
                        )
                        result.errors.append(error_msg)

                # Check for holders that are no longer in the API response (removed holders)
                # Only check holders for the current token being processed
                for db_holder in db_holders:
                    try:
                        # Only process holders for the current token
                        if db_holder.token_id != token.id:
                            continue

                        # Use address for matching since that's what we get from the API
                        if (
                            db_holder.address
                            and db_holder.address not in api_holders_by_contract
                        ):
                            # This holder is no longer holding tokens for this specific token, remove from database
                            logger.info(
                                "Removing holder for token (no longer holds tokens)",
                                extra={
                                    "task": "dao_token_holders_monitor",
                                    "address": db_holder.address,
                                    "token_name": token.name,
                                },
                            )
                            backend.delete_holder(db_holder.id)
                            result.holders_removed += 1
                    except Exception as e:
                        logger.error(
                            "Error processing holder",
                            extra={
                                "task": "dao_token_holders_monitor",
                                "holder_id": db_holder.id,
                                "address": db_holder.address,
                                "token_name": token.name,
                                "error": str(e),
                            },
                        )
                        continue

                await asyncio.sleep(
                    1
                )  # Add sleep to space out API calls between tokens
                return  # Success, exit retry loop

            except HiroApiRateLimitError as e:
                if attempt == max_retries - 1:
                    error_msg = (
                        f"Max retries reached for token after rate limit: {str(e)}"
                    )
                    logger.error(
                        error_msg,
                        extra={
                            "task": "dao_token_holders_monitor",
                            "token_id": token.id,
                            "attempt": attempt,
                        },
                    )
                    result.errors.append(error_msg)
                    return
                backoff = 2**attempt  # Exponential backoff (1s, 2s, 4s)
                logger.warning(
                    f"Rate limit hit for token, retrying after {backoff}s",
                    extra={
                        "task": "dao_token_holders_monitor",
                        "token_id": token.id,
                        "attempt": attempt,
                    },
                )
                await asyncio.sleep(backoff)  # Async sleep for retry

            except Exception as e:
                error_msg = f"Error syncing holders for token: {str(e)}"
                logger.error(
                    error_msg,
                    extra={"task": "dao_token_holders_monitor", "token_id": token.id},
                    exc_info=True,
                )
                result.errors.append(error_msg)
                return  # Don't retry non-rate-limit errors

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DaoTokenHoldersMonitorResult]:
        """Execute DAO token holders monitoring task."""
        logger.info(
            "Starting DAO token holders monitoring task",
            extra={"task": "dao_token_holders_monitor"},
        )

        result = DaoTokenHoldersMonitorResult(
            success=True, message="DAO token holders sync completed"
        )

        try:
            # Get all tokens from the database
            all_tokens = backend.list_tokens()
            logger.info(
                "Found tokens to process",
                extra={
                    "task": "dao_token_holders_monitor",
                    "token_count": len(all_tokens),
                },
            )

            if not all_tokens:
                result.message = "No tokens found to process"
                return [result]

            # Process each token
            for token in all_tokens:
                try:
                    logger.info(
                        "Processing token",
                        extra={
                            "task": "dao_token_holders_monitor",
                            "token_name": token.name,
                            "token_id": token.id,
                        },
                    )
                    await self._sync_token_holders(
                        token, result
                    )  # Now async-friendly with sleeps
                    result.tokens_processed += 1
                    await asyncio.sleep(
                        1
                    )  # Additional brief sleep between tokens for extra safety

                except Exception as e:
                    error_msg = "Error processing token"
                    logger.error(
                        error_msg,
                        extra={
                            "task": "dao_token_holders_monitor",
                            "token_id": token.id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                    result.errors.append(error_msg)
                    # Continue processing other tokens even if one fails

            # Update result message with summary
            summary = (
                f"Processed {result.tokens_processed} tokens. "
                f"Created {result.holders_created}, updated {result.holders_updated}, "
                f"removed {result.holders_removed} holders. "
                f"Queued {result.approvals_queued} proposal approvals."
            )

            if result.errors:
                summary += f" Encountered {len(result.errors)} errors."
                result.success = False

            result.message = summary
            logger.info(summary, extra={"task": "dao_token_holders_monitor"})

            return [result]

        except Exception as e:
            error_msg = "Error executing DAO token holders monitoring task"
            logger.error(
                error_msg,
                extra={"task": "dao_token_holders_monitor", "error": str(e)},
                exc_info=True,
            )
            return [
                DaoTokenHoldersMonitorResult(
                    success=False, message=error_msg, error=e, errors=[error_msg]
                )
            ]


# Create instance for auto-registration
dao_token_holders_monitor = DaoTokenHoldersMonitorTask()
