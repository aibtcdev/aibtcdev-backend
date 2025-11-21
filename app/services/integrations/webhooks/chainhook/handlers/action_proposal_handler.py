"""Handler for capturing new DAO action proposals."""

import hashlib
import random
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import (
    AgentWithWalletTokenDTO,
    ContractStatus,
    LotteryResultCreate,
    ProposalBase,
    ProposalCreate,
    ProposalFilter,
    ProposalType,
    QueueMessageCreate,
    QueueMessageType,
)
from app.config import config
from app.services.integrations.webhooks.chainhook.handlers.lottery_utils import (
    LotterySelection,
    QuorumCalculator,
    create_wallet_selection_dict,
    extract_wallet_ids_from_selection,
)
from app.lib.utils import decode_hex_parameters
from app.services.integrations.webhooks.chainhook.handlers.base_proposal_handler import (
    BaseProposalHandler,
)
from app.services.integrations.webhooks.chainhook.models import (
    Event,
    TransactionWithReceipt,
)
from app.services.ai.simple_workflows import generate_proposal_metadata


class ActionProposalHandler(BaseProposalHandler):
    """Handler for capturing and processing new DAO action proposals.

    This handler identifies contract calls related to proposing actions through agent account contracts,
    creates proposal records in the database, and tracks their lifecycle including failed proposals.
    """

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions related to proposing actions
        through agent account contracts. It handles both successful and failed transactions.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]

        # Only handle ContractCall type transactions
        if not isinstance(tx_kind, dict):
            self.logger.debug(f"Skipping: tx_kind is not a dict: {type(tx_kind)}")
            return False

        tx_kind_type = tx_kind.get("type")

        if not isinstance(tx_data_content, dict):
            self.logger.debug(
                f"Skipping: tx_data_content is not a dict: {type(tx_data_content)}"
            )
            return False

        # Check if the method name is exactly "create-action-proposal"
        tx_method = tx_data_content.get("method", "")
        is_proposal_method = tx_method == "create-action-proposal"

        # Check if this is an agent account contract (typically has pattern like "aibtc-acct-*")
        contract_identifier = tx_data_content.get("contract_identifier", "")
        is_agent_account = "aibtc-acct-" in contract_identifier

        if is_proposal_method and is_agent_account:
            self.logger.debug(
                f"Found action proposal method: {tx_method} in agent account: {contract_identifier}"
            )

        # Handle both successful and failed proposal creation attempts
        return (
            tx_kind_type == "ContractCall" and is_proposal_method and is_agent_account
        )

    def _get_dao_from_args(self, args: List[str]) -> Optional[Dict]:
        """Extract DAO information from transaction arguments.

        Args:
            args: Transaction arguments list

        Returns:
            Optional[Dict]: DAO data if found, None otherwise
        """
        if not args or len(args) < 1:
            self.logger.warning("No arguments found in transaction")
            return None

        # First argument is the proposal contract (DAO extension)
        proposal_contract = args[0]
        self.logger.debug(
            f"Looking for DAO with proposal contract: {proposal_contract}"
        )

        # Try to find DAO by the proposal contract (extension)
        dao_data = self._find_dao_for_contract(proposal_contract)

        if dao_data:
            return dao_data

        # If not found, try to find by base DAO contract
        # Extract the base contract address from the proposal contract
        if "." in proposal_contract:
            base_address = proposal_contract.split(".")[0]
            # Look for DAOs with this base address
            self.logger.debug(f"Trying to find DAO with base address: {base_address}")

            # This is a fallback - we may need to implement a more sophisticated lookup
            # For now, try common DAO contract patterns
            possible_dao_contracts = [
                f"{base_address}.dao",
                f"{base_address}.base-dao",
                f"{base_address}.aibtc-dao",
            ]

            for dao_contract in possible_dao_contracts:
                dao_data = self._find_dao_for_contract(dao_contract)
                if dao_data:
                    self.logger.debug(f"Found DAO using contract: {dao_contract}")
                    return dao_data

        self.logger.warning(f"No DAO found for proposal contract: {proposal_contract}")
        return None

    def _get_proposal_info_from_args(
        self, args: List[str], tx_id: str, tx_success: bool
    ) -> Optional[Dict]:
        """Extract proposal information from transaction arguments.

        Args:
            args: Transaction arguments list
            tx_id: Transaction ID
            tx_success: Whether the transaction was successful

        Returns:
            Optional[Dict]: Dictionary containing proposal information if found, None otherwise
        """
        if not args or len(args) < 3:
            self.logger.warning(
                f"Insufficient arguments in transaction {tx_id}, got {len(args) if args else 0} args"
            )
            return None

        proposal_contract = args[0]  # DAO extension contract for proposals
        action_contract = args[1]  # Action contract to execute
        parameters_hex = args[2]  # Parameters for the action
        memo = args[3] if len(args) > 3 else None

        # Clean up memo if it's in Clarity format
        if memo and memo.startswith("(some "):
            # Remove '(some "' prefix and '")' suffix
            memo = memo[6:-2] if memo.endswith('")') else memo[6:]

        # For failed transactions, we create a synthetic proposal info
        if not tx_success:
            return {
                "proposal_id": None,  # No proposal ID for failed transactions
                "action": action_contract,
                "caller": None,
                "creator": None,
                "liquid_tokens": "0",
                "parameters": parameters_hex,
                "bond": "0",
                "contract_caller": proposal_contract,  # Updated to use proposal contract
                "created_btc": None,
                "created_stx": None,
                "creator_user_id": None,
                "exec_end": None,
                "exec_start": None,
                "memo": memo,
                "tx_sender": None,
                "vote_end": None,
                "vote_start": None,
                "voting_delay": None,
                "voting_period": None,
                "voting_quorum": None,
                "voting_reward": None,
                "voting_threshold": None,
                "is_failed": True,  # Mark as failed
            }

        # For successful transactions, try to get info from events first
        # but if no events, create from args
        return {
            "proposal_id": None,  # Will be populated from events if available
            "action": action_contract,
            "caller": None,
            "creator": None,
            "liquid_tokens": "0",
            "parameters": parameters_hex,
            "bond": "0",
            "contract_caller": proposal_contract,  # Updated to use proposal contract
            "created_btc": None,
            "created_stx": None,
            "creator_user_id": None,
            "exec_end": None,
            "exec_start": None,
            "memo": memo,
            "tx_sender": None,
            "vote_end": None,
            "vote_start": None,
            "voting_delay": None,
            "voting_period": None,
            "voting_quorum": None,
            "voting_reward": None,
            "voting_threshold": None,
            "is_failed": False,
        }

    def _get_proposal_info_from_events(self, events: list[Event]) -> Optional[Dict]:
        """Extract the action proposal information from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing proposal information if found, None otherwise
        """
        # First try to find the comprehensive proposal data from the DAO contract event
        dao_proposal_info = None
        agent_proposal_info = None

        for event in events:
            # Find SmartContractEvent events
            if event.type != "SmartContractEvent" or not hasattr(event, "data"):
                continue

            event_data = event.data

            # Check if this is a print event
            if event_data.get("topic") != "print":
                continue

            # Get the value, which might be None
            value = event_data.get("value")

            # Skip events with null values
            if value is None:
                self.logger.debug("Value is None in SmartContractEvent data")
                continue

            # Check notification type
            notification = value.get("notification", "")

            # Look for DAO contract event (contains comprehensive proposal data)
            if "action-proposal-voting/create-action-proposal" in notification:
                payload = value.get("payload", {})
                if payload:
                    dao_proposal_info = {
                        "proposal_id": payload.get("proposalId"),
                        "action": payload.get("action"),
                        "caller": payload.get("caller"),
                        "creator": payload.get("creator"),
                        "liquid_tokens": str(payload.get("liquidTokens", "0")),
                        "parameters": payload.get("parameters"),
                        "bond": str(payload.get("bond", "0")),
                        # Fields from updated payload
                        "contract_caller": payload.get("contractCaller"),
                        "created_btc": payload.get("createdBtc"),
                        "created_stx": payload.get("createdStx"),
                        "creator_user_id": payload.get("creatorUserId"),
                        "exec_end": payload.get("execEnd"),
                        "exec_start": payload.get("execStart"),
                        "memo": payload.get("memo"),
                        "tx_sender": payload.get("txSender"),
                        "vote_end": payload.get("voteEnd"),
                        "vote_start": payload.get("voteStart"),
                        "voting_delay": payload.get("votingDelay"),
                        "voting_period": payload.get("votingPeriod"),
                        "voting_quorum": payload.get("votingQuorum"),
                        "voting_reward": (
                            str(payload.get("votingReward"))
                            if payload.get("votingReward") is not None
                            else None
                        ),
                        "voting_threshold": payload.get("votingThreshold"),
                        "is_failed": False,
                    }

            # Look for agent account event (fallback for basic info)
            elif "aibtc-agent-account/create-action-proposal" in notification:
                payload = value.get("payload", {})
                if payload:
                    agent_proposal_info = {
                        "proposal_id": None,  # Agent event doesn't have proposal ID
                        "action": payload.get("action"),
                        "caller": payload.get("caller"),
                        "creator": None,
                        "liquid_tokens": "0",
                        "parameters": payload.get("parameters"),
                        "bond": "0",
                        # Fields from agent payload
                        "contract_caller": payload.get(
                            "proposalContract"
                        ),  # Different field name
                        "created_btc": None,
                        "created_stx": None,
                        "creator_user_id": None,
                        "exec_end": None,
                        "exec_start": None,
                        "memo": None,
                        "tx_sender": payload.get("sender"),
                        "vote_end": None,
                        "vote_start": None,
                        "voting_delay": None,
                        "voting_period": None,
                        "voting_quorum": None,
                        "voting_reward": None,
                        "voting_threshold": None,
                        "is_failed": False,
                    }

            # Legacy format support
            elif notification == "create-action-proposal" or notification.endswith(
                "/create-action-proposal"
            ):
                payload = value.get("payload", {})
                if payload:
                    return {
                        "proposal_id": payload.get("proposalId"),
                        "action": payload.get("action"),
                        "caller": payload.get("caller"),
                        "creator": payload.get("creator"),
                        "liquid_tokens": str(payload.get("liquidTokens", "0")),
                        "parameters": payload.get("parameters"),
                        "bond": str(payload.get("bond", "0")),
                        # Fields from updated payload
                        "contract_caller": payload.get("contractCaller"),
                        "created_btc": payload.get("createdBtc"),
                        "created_stx": payload.get("createdStx"),
                        "creator_user_id": payload.get("creatorUserId"),
                        "exec_end": payload.get("execEnd"),
                        "exec_start": payload.get("execStart"),
                        "memo": payload.get("memo"),
                        "tx_sender": payload.get("txSender"),
                        "vote_end": payload.get("voteEnd"),
                        "vote_start": payload.get("voteStart"),
                        "voting_delay": payload.get("votingDelay"),
                        "voting_period": payload.get("votingPeriod"),
                        "voting_quorum": payload.get("votingQuorum"),
                        "voting_reward": (
                            str(payload.get("votingReward"))
                            if payload.get("votingReward") is not None
                            else None
                        ),
                        "voting_threshold": payload.get("votingThreshold"),
                        "is_failed": False,
                    }

        # Prefer DAO contract info (comprehensive) over agent info (basic)
        if dao_proposal_info:
            self.logger.debug(
                "Found comprehensive proposal info from DAO contract event"
            )
            return dao_proposal_info
        elif agent_proposal_info:
            self.logger.debug("Found basic proposal info from agent account event")
            return agent_proposal_info

        return None

    def _sanitize_string(self, input_string: Optional[str]) -> Optional[str]:
        """Sanitize string by removing null bytes and other invalid characters.

        Args:
            input_string: The string to sanitize

        Returns:
            A sanitized string or None if input was None
        """
        if input_string is None:
            return None

        # Replace null bytes and other control characters
        sanitized = ""
        for char in input_string:
            if (
                ord(char) >= 32 or char in "\n\r\t"
            ):  # Keep printable chars and some whitespace
                sanitized += char

        return sanitized

    def _get_agent_token_holders(self, dao_id: UUID) -> List[AgentWithWalletTokenDTO]:
        """Get agents that hold tokens for the given DAO.

        Args:
            dao_id: The ID of the DAO

        Returns:
            List[AgentWithWalletTokenDTO]: List of agents with their wallet and token data
        """
        # Use the specialized backend method for getting agents with DAO tokens
        agents_with_tokens_dto = backend.get_agents_with_dao_tokens(dao_id)

        if not agents_with_tokens_dto:
            self.logger.error(f"No agents found with tokens for DAO {dao_id}")
            return []

        self.logger.info(
            f"Found {len(agents_with_tokens_dto)} agents holding tokens for DAO {dao_id}"
        )

        return agents_with_tokens_dto

    def _conduct_quorum_lottery(
        self,
        agents_with_tokens: List[AgentWithWalletTokenDTO],
        proposal_liquid_tokens: str,
        bitcoin_block_hash: str,
        bitcoin_block_height: int,
    ) -> LotterySelection:
        """Conduct a quorum-aware lottery to select agents for voting.

        Args:
            agents_with_tokens: List of agents with their token amounts
            proposal_liquid_tokens: Total liquid tokens from proposal
            bitcoin_block_hash: Bitcoin block hash to use as seed
            bitcoin_block_height: Bitcoin block height for transparency/logging/visual ID (not used in seed/selection)

        Returns:
            LotterySelection: Complete lottery results with quorum tracking
        """
        try:
            _ = int(proposal_liquid_tokens or "0")
        except ValueError as e:
            self.logger.warning(
                f"Invalid proposal_liquid_tokens '{proposal_liquid_tokens}': {e} - returning empty selection"
            )
            return LotterySelection()

        selection = LotterySelection()

        if not agents_with_tokens:
            self.logger.warning("No agents with tokens available for lottery")
            return selection

        # Apply minimum token threshold filter
        min_threshold = config.lottery.min_token_threshold
        filtered_agents = [
            agent
            for agent in agents_with_tokens
            if int(agent.token_amount or "0") >= min_threshold
        ]
        total_filtered = len(filtered_agents)
        total_original = len(agents_with_tokens)

        if total_filtered == 0:
            self.logger.warning(
                f"No agents meet min_token_threshold={min_threshold}, falling back to all {total_original} agents"
            )
            filtered_agents = agents_with_tokens
            total_filtered = total_original

        self.logger.info(
            f"Lottery filtering: {total_original} total agents → {total_filtered} eligible (>= {min_threshold} tokens)"
        )

        # Use filtered agents for the rest of the process
        agents_with_tokens = filtered_agents  # Override for consistency

        # Initialize lottery parameters using config
        selection.liquid_tokens_at_creation = proposal_liquid_tokens
        selection.quorum_percentage = config.lottery.quorum_percentage
        selection.total_eligible_wallets = len(agents_with_tokens)
        selection.total_eligible_tokens = (
            QuorumCalculator.calculate_total_eligible_tokens(agents_with_tokens)
        )
        selection.quorum_threshold = QuorumCalculator.calculate_quorum_threshold(
            proposal_liquid_tokens, config.lottery.quorum_percentage
        )

        self.logger.info(
            f"Starting quorum lottery: {len(agents_with_tokens)} eligible agents, "
            f"liquid tokens: {proposal_liquid_tokens}, quorum needed: {selection.quorum_threshold} "
            f"(max_selections={config.lottery.max_selections})"
        )

        # Check if quorum is achievable
        if not QuorumCalculator.is_quorum_achievable(
            proposal_liquid_tokens,
            selection.total_eligible_tokens,
            config.lottery.quorum_percentage,
        ):
            self.logger.warning(
                f"Quorum not achievable: need {selection.quorum_threshold} tokens, "
                f"only {selection.total_eligible_tokens} available. Selecting all agents."
            )
            # Select all available agents
            for agent in agents_with_tokens:
                selection.selected_wallets.append(
                    create_wallet_selection_dict(agent.wallet_id, agent.token_amount)
                )
            selection.total_selected_tokens = selection.total_eligible_tokens
            selection.quorum_achieved = False
            selection.selection_rounds = 1
            return selection

        # Create deterministic seed from Bitcoin block hash
        seed = hashlib.sha256(bitcoin_block_hash.encode()).hexdigest()

        # Conduct weighted lottery until quorum is met or max selections reached
        remaining_agents = agents_with_tokens.copy()
        selected_tokens = Decimal("0")
        quorum_threshold_decimal = Decimal(selection.quorum_threshold)

        round_number = 0
        while (
            selected_tokens < quorum_threshold_decimal
            and remaining_agents
            and len(selection.selected_wallets) < config.lottery.max_selections
        ):
            round_number += 1

            round_seed = f"{seed}_{round_number}"
            random.seed(round_seed)

            selected_agent = self._perform_weighted_selection(remaining_agents)

            wallet_dict = create_wallet_selection_dict(
                selected_agent.wallet_id, selected_agent.token_amount
            )
            selection.selected_wallets.append(wallet_dict)

            selected_tokens += Decimal(selected_agent.token_amount)

            self.logger.debug(
                f"Round {round_number}: Selected agent {selected_agent.agent_id} "
                f"with {selected_agent.token_amount} tokens "
                f"(total: {selected_tokens}/{selection.quorum_threshold})"
            )

        # Finalize selection results
        selection.total_selected_tokens = str(selected_tokens)
        selection.quorum_achieved = selected_tokens >= quorum_threshold_decimal
        selection.selection_rounds = round_number

        # Ensure minimum selection for fairness
        min_agents = min(config.lottery.min_selections, len(agents_with_tokens))
        while (
            len(selection.selected_wallets) < min_agents
            and remaining_agents
            and len(selection.selected_wallets) < config.lottery.max_selections
        ):
            round_number += 1
            round_seed = f"{seed}_{round_number}"
            random.seed(round_seed)

            selected_agent = self._perform_weighted_selection(remaining_agents)

            wallet_dict = create_wallet_selection_dict(
                selected_agent.wallet_id, selected_agent.token_amount
            )
            selection.selected_wallets.append(wallet_dict)

            selected_tokens += Decimal(selected_agent.token_amount)

        # Update final totals
        selection.total_selected_tokens = str(selected_tokens)
        selection.quorum_achieved = selected_tokens >= quorum_threshold_decimal
        selection.selection_rounds = round_number

        self.logger.info(
            f"Quorum lottery completed: selected {len(selection.selected_wallets)} agents "
            f"with {selection.total_selected_tokens} tokens "
            f"({'✓' if selection.quorum_achieved else '✗'} quorum {'achieved' if selection.quorum_achieved else 'not achieved'}) "
            f"(cfg: min_th={min_threshold}, max_sel={config.lottery.max_selections}, min_sel={config.lottery.min_selections})"
        )

        return selection

    def _perform_weighted_selection(
        self, remaining_agents: List[AgentWithWalletTokenDTO]
    ) -> AgentWithWalletTokenDTO:
        """Perform a single round of weighted random agent selection (assumes random is seeded)."""
        weights = [int(agent.token_amount or "0") for agent in remaining_agents]
        if not weights or all(w == 0 for w in weights):
            self.logger.warning("All remaining weights are zero, using equal weights")
            weights = [1] * len(remaining_agents)

        total_weight = sum(weights)
        rand_int = random.randrange(total_weight)

        cumulative = 0
        selected_idx = 0
        for idx, weight in enumerate(weights):
            cumulative += weight
            if rand_int < cumulative:
                selected_idx = idx
                break

        return remaining_agents.pop(selected_idx)

    def _create_fallback_lottery_result(
        self,
        proposal,
        dao_id: UUID,
        agents: List[AgentWithWalletTokenDTO],
        bitcoin_block_height: int,
        bitcoin_block_hash: Optional[str],
        lottery_selection: LotterySelection,
        is_update: bool = False,
    ):
        """
        Create a fallback lottery result by selecting up to max_selections agents.

        Args:
            proposal: The proposal object for which the lottery result is being created.
            dao_id (UUID): The UUID of the DAO.
            agents (List[AgentWithWalletTokenDTO]): List of agent objects with their token amounts.
            bitcoin_block_height (int): The Bitcoin block height used for the lottery.
            bitcoin_block_hash (Optional[str]): The Bitcoin block hash, or None to use a fallback.
            lottery_selection (LotterySelection): The LotterySelection object to populate with selected wallets.
            is_update (bool, optional): Whether this is an update path. Defaults to False.

        Returns:
            LotteryResult: The created lottery result object.

        """
        # Apply minimum token threshold filter for consistency with main lottery path
        min_threshold = config.lottery.min_token_threshold
        filtered_agents = [
            agent for agent in agents if int(agent.token_amount or "0") >= min_threshold
        ]
        total_filtered = len(filtered_agents)
        total_original = len(agents)

        if total_filtered == 0:
            self.logger.warning(
                f"No agents meet min_token_threshold={min_threshold}, falling back to all {total_original} agents"
            )
            filtered_agents = agents
            total_filtered = total_original

        self.logger.info(
            f"Fallback filtering: {total_original} total agents → {total_filtered} eligible (>= {min_threshold} tokens)"
        )

        for agent in filtered_agents[: config.lottery.max_selections]:
            lottery_selection.selected_wallets.append(
                create_wallet_selection_dict(agent.wallet_id, agent.token_amount)
            )

        fallback_bitcoin_hash = (
            bitcoin_block_hash or f"fallback-hash{'-update' if is_update else ''}"
        )
        fallback_suffix = "-fallback-update" if is_update else "-fallback"
        lottery_seed = hashlib.sha256(
            f"{fallback_bitcoin_hash}{fallback_suffix}".encode()
        ).hexdigest()

        lottery_result = backend.create_lottery_result(
            LotteryResultCreate(
                proposal_id=proposal.id,
                dao_id=dao_id,
                bitcoin_block_height=bitcoin_block_height,
                bitcoin_block_hash=fallback_bitcoin_hash,
                lottery_seed=lottery_seed,
                selected_wallets=lottery_selection.selected_wallets,
                liquid_tokens_at_creation=proposal.liquid_tokens or "0",
                quorum_threshold="0",
                total_selected_tokens=str(
                    sum(
                        int(w.get("token_amount", "0"))
                        for w in lottery_selection.selected_wallets
                    )
                ),
                quorum_achieved=False,
                quorum_percentage=config.lottery.quorum_percentage,
                total_eligible_wallets=len(agents),
                total_eligible_tokens=str(
                    sum(int(agent.token_amount or "0") for agent in agents)
                ),
                selection_rounds=1,
                selected_wallet_ids=extract_wallet_ids_from_selection(
                    lottery_selection.selected_wallets
                ),
            )
        )
        return lottery_result

    async def _parse_and_generate_proposal_metadata(
        self, parameters: str, dao_name: str, proposal_id: str
    ) -> Dict[str, str]:
        """Parse proposal content for title/tags and generate summary using AI agent.

        First parses the proposal content looking for the structured format:
        - Original message
        - "\n\n--- Metadata ---" (metadata section marker)
        - "\nTitle: {title}" if there's a title
        - "\nTags: {tags_string}" where tags_string is tags joined by "|"

        Then uses ProposalMetadataAgent to generate a summary and fill in missing components.

        Args:
            parameters: The decoded proposal parameters/content
            dao_name: Name of the DAO
            proposal_id: The proposal ID

        Returns:
            Dict containing 'title', 'summary', and 'tags' keys
        """
        if not parameters:
            return {
                "title": f"Action Proposal #{proposal_id}",
                "summary": "",
                "tags": [],
            }

        # Parse content for structured metadata section
        parsed_title = ""
        parsed_tags = []
        base_content = parameters

        # Look for metadata section: "--- Metadata ---"
        metadata_marker = "--- Metadata ---"
        if metadata_marker in parameters:
            parts = parameters.split(metadata_marker, 1)
            if len(parts) == 2:
                base_content = parts[0].strip()
                metadata_section = parts[1].strip()

                # Parse metadata section line by line
                for line in metadata_section.split("\n"):
                    line = line.strip()
                    if line.startswith("Title: "):
                        parsed_title = line[7:].strip()  # Remove "Title: " prefix
                    elif line.startswith("Tags: "):
                        tags_string = line[6:].strip()  # Remove "Tags: " prefix
                        if "|" in tags_string:
                            parsed_tags = [
                                tag.strip()
                                for tag in tags_string.split("|")
                                if tag.strip()
                            ]

        # Clean base content for AI processing
        clean_content = base_content.strip()

        # Use generate_proposal_metadata to generate summary and fill missing components
        try:
            # Use clean content for AI processing
            proposal_content = clean_content or f"Action proposal {proposal_id}"

            # Generate metadata using AI
            ai_result = await generate_proposal_metadata(
                proposal_content=proposal_content,
                dao_name=dao_name,
                proposal_type="action",
            )

            # Combine parsed and AI-generated results
            final_title = (
                parsed_title
                if parsed_title
                else (
                    ai_result.get("title", f"Action Proposal #{proposal_id}")
                    if "error" not in ai_result
                    else f"Action Proposal #{proposal_id}"
                )
            )

            final_tags = (
                parsed_tags
                if parsed_tags
                else (ai_result.get("tags", []) if "error" not in ai_result else [])
            )

            # Always use AI-generated summary as it's specifically designed for summarization
            final_summary = (
                ai_result.get("summary", clean_content)
                if "error" not in ai_result
                else clean_content
            )

            self.logger.info(
                f"Combined metadata for proposal {proposal_id} - "
                f"Title: '{final_title}' (parsed: {bool(parsed_title)}), "
                f"Tags: {final_tags} (parsed: {bool(parsed_tags)}), "
                f"Summary: AI-generated"
            )

            return {
                "title": final_title,
                "summary": final_summary,
                "tags": final_tags,
            }

        except Exception as e:
            self.logger.error(
                f"Error in AI metadata generation for proposal {proposal_id}: {str(e)}"
            )

            # Fallback to parsed results with defaults
            return {
                "title": (
                    parsed_title if parsed_title else f"Action Proposal #{proposal_id}"
                ),
                "summary": clean_content,
                "tags": parsed_tags,
            }

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle action proposal transactions.

        Processes new action proposal transactions (both successful and failed) and creates proposal records in the database.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Get transaction arguments
        args = tx_data_content.get("args", [])
        if not args:
            self.logger.warning(f"No arguments found in transaction {tx_id}")
            return

        # Find the DAO using the first argument (DAO contract)
        dao_data = self._get_dao_from_args(args)
        if not dao_data:
            dao_contract = args[0] if args else "unknown"
            self.logger.warning(f"No DAO found for contract {dao_contract}")
            return

        # Get transaction success status
        tx_success = tx_metadata.success

        # Get Bitcoin block information for lottery seeding
        bitcoin_block_height = (
            tx_metadata.bitcoin_block_height
            if hasattr(tx_metadata, "bitcoin_block_height")
            else None
        )
        bitcoin_block_hash = (
            tx_metadata.bitcoin_block_hash
            if hasattr(tx_metadata, "bitcoin_block_hash")
            else None
        )

        # If we don't have Bitcoin block info from tx metadata, try to get latest chain state
        if not bitcoin_block_hash:
            latest_chain_state = backend.get_latest_chain_state("mainnet")
            if latest_chain_state:
                bitcoin_block_height = latest_chain_state.bitcoin_block_height
                bitcoin_block_hash = latest_chain_state.block_hash
                self.logger.debug(
                    f"Using latest chain state Bitcoin block: {bitcoin_block_height}"
                )

        # Get the proposal info from the transaction arguments
        proposal_info = self._get_proposal_info_from_args(args, tx_id, tx_success)
        if proposal_info is None:
            self.logger.warning(
                f"Could not determine proposal information from transaction {tx_id}"
            )
            return

        # If transaction was successful, try to get additional info from events
        if tx_success:
            events = (
                tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
            )
            event_info = self._get_proposal_info_from_events(events)
            if event_info:
                # Merge event info with args info, preferring event info for populated fields
                for key, value in event_info.items():
                    if value is not None:
                        proposal_info[key] = value

        self.logger.info(
            f"Processing {'successful' if tx_success else 'failed'} action proposal for DAO {dao_data['name']} "
            f"(Proposal contract: {args[0]}, tx_id: {tx_id})"
        )

        # Check if the proposal already exists in the database
        existing_proposals = backend.list_proposals(
            filters=ProposalFilter(
                tx_id=tx_id,
            )
        )

        if not existing_proposals:
            try:
                # First try to decode parameters as hex
                decoded_parameters = decode_hex_parameters(proposal_info["parameters"])

                # Sanitize the decoded parameters to remove null bytes and invalid characters
                if decoded_parameters is not None:
                    parameters = self._sanitize_string(decoded_parameters)
                    self.logger.debug(
                        f"Decoded and sanitized parameters: {parameters[:100]}..."
                    )
                else:
                    parameters = proposal_info["parameters"]
                    self.logger.debug("Using original parameters (hex decoding failed)")

                # Parse title/tags from content and generate summary using AI
                proposal_id_str = str(proposal_info.get("proposal_id", "failed"))
                metadata = await self._parse_and_generate_proposal_metadata(
                    parameters, dao_data["name"], proposal_id_str
                )

                # Determine contract status based on transaction success
                contract_status = (
                    ContractStatus.DEPLOYED if tx_success else ContractStatus.FAILED
                )

                # Create a new proposal record in the database
                proposal = backend.create_proposal(
                    ProposalCreate(
                        dao_id=dao_data["id"],
                        title=metadata["title"],
                        content=parameters,
                        summary=metadata["summary"],
                        contract_principal=args[
                            0
                        ],  # Use proposal contract as principal
                        tx_id=tx_id,
                        proposal_id=proposal_info["proposal_id"],
                        status=contract_status,
                        type=ProposalType.ACTION,
                        # Add fields from payload
                        action=proposal_info["action"],
                        caller=proposal_info["caller"],
                        creator=proposal_info["creator"],
                        liquid_tokens=proposal_info["liquid_tokens"],
                        bond=proposal_info["bond"],
                        # Fields from updated payload
                        contract_caller=proposal_info["contract_caller"],
                        created_btc=proposal_info["created_btc"],
                        created_stx=proposal_info["created_stx"],
                        creator_user_id=proposal_info["creator_user_id"],
                        exec_end=proposal_info["exec_end"],
                        exec_start=proposal_info["exec_start"],
                        memo=proposal_info["memo"],
                        tx_sender=proposal_info["tx_sender"],
                        vote_end=proposal_info["vote_end"],
                        vote_start=proposal_info["vote_start"],
                        voting_delay=proposal_info["voting_delay"],
                        voting_period=proposal_info["voting_period"],
                        voting_quorum=proposal_info["voting_quorum"],
                        voting_reward=proposal_info["voting_reward"],
                        voting_threshold=proposal_info["voting_threshold"],
                    )
                )
                self.logger.info(
                    f"Created new {'successful' if tx_success else 'failed'} action proposal record in database: {proposal.id}"
                )

                # Queue evaluation messages for proposals with agents holding governance tokens
                # Note: Removing tx_success check to debug lottery creation issues
                self.logger.info(
                    f"Starting lottery process for proposal {proposal.id} (tx_success: {tx_success})"
                )

                agents = self._get_agent_token_holders(dao_data["id"])
                self.logger.info(
                    f"Found {len(agents) if agents else 0} agents with tokens for DAO {dao_data['id']}"
                )

                if agents:
                    # Conduct quorum-aware lottery
                    lottery_selection = LotterySelection()
                    self.logger.info(
                        f"Bitcoin block hash available: {bool(bitcoin_block_hash)}"
                    )
                    self.logger.info(
                        f"Proposal liquid tokens: {proposal.liquid_tokens}"
                    )
                    self.logger.info(f"Bitcoin block height: {bitcoin_block_height}")

                    if bitcoin_block_hash and proposal.liquid_tokens:
                        self.logger.info(
                            "Conditions met for full lottery - conducting quorum lottery"
                        )
                        lottery_selection = self._conduct_quorum_lottery(
                            agents,
                            proposal.liquid_tokens,
                            bitcoin_block_hash,
                            bitcoin_block_height or 0,
                        )

                        self.logger.info(
                            f"Lottery selection completed: {len(lottery_selection.selected_wallets)} wallets selected"
                        )

                        # Record the lottery results
                        try:
                            self.logger.info(
                                "Attempting to create lottery result in database"
                            )
                            lottery_result = backend.create_lottery_result(
                                LotteryResultCreate(
                                    proposal_id=proposal.id,
                                    dao_id=dao_data["id"],
                                    bitcoin_block_height=bitcoin_block_height,
                                    bitcoin_block_hash=bitcoin_block_hash,
                                    lottery_seed=hashlib.sha256(
                                        bitcoin_block_hash.encode()
                                    ).hexdigest(),
                                    selected_wallets=lottery_selection.selected_wallets,
                                    liquid_tokens_at_creation=lottery_selection.liquid_tokens_at_creation,
                                    quorum_threshold=lottery_selection.quorum_threshold,
                                    total_selected_tokens=lottery_selection.total_selected_tokens,
                                    quorum_achieved=lottery_selection.quorum_achieved,
                                    quorum_percentage=lottery_selection.quorum_percentage,
                                    total_eligible_wallets=lottery_selection.total_eligible_wallets,
                                    total_eligible_tokens=lottery_selection.total_eligible_tokens,
                                    selection_rounds=lottery_selection.selection_rounds,
                                    # Backward compatibility
                                    selected_wallet_ids=extract_wallet_ids_from_selection(
                                        lottery_selection.selected_wallets
                                    ),
                                )
                            )
                            self.logger.info(
                                f"Successfully created lottery result with ID: {lottery_result.id}"
                            )
                        except Exception as lottery_error:
                            self.logger.error(
                                f"Failed to create lottery result: {str(lottery_error)}"
                            )
                            self.logger.error(
                                f"Lottery data: proposal_id={proposal.id}, dao_id={dao_data['id']}, "
                                f"bitcoin_block_height={bitcoin_block_height}, bitcoin_block_hash={bitcoin_block_hash}"
                            )
                            raise

                            self.logger.info(
                                f"Quorum lottery completed for proposal {proposal.id}: "
                                f"selected {len(lottery_selection.selected_wallets)} agents "
                                f"({'✓' if lottery_selection.quorum_achieved else '✗'} quorum achieved)"
                            )
                    else:
                        # Fallback: use old system if no Bitcoin block hash or liquid tokens
                        self.logger.warning(
                            "Bitcoin block hash or liquid tokens missing - using fallback lottery"
                        )
                        fallback_bitcoin_height = bitcoin_block_height or 0
                        try:
                            lottery_result = self._create_fallback_lottery_result(
                                proposal,
                                dao_data["id"],
                                agents,
                                fallback_bitcoin_height,
                                bitcoin_block_hash,
                                lottery_selection,
                                is_update=False,
                            )
                            self.logger.info(
                                f"Successfully created fallback lottery result with ID: {lottery_result.id}"
                            )
                        except Exception as fallback_error:
                            self.logger.error(
                                f"Fallback lottery failed for proposal {proposal.id}, dao {dao_data['id']}: {str(fallback_error)}"
                            )
                            raise

                    # Create evaluation queue messages for selected agents only
                    selected_wallet_ids = extract_wallet_ids_from_selection(
                        lottery_selection.selected_wallets
                    )
                    self.logger.info(
                        f"Creating queue messages for {len(selected_wallet_ids)} selected wallets"
                    )

                    for wallet_id in selected_wallet_ids:
                        message_data = {
                            "proposal_id": proposal.id,  # Only pass the proposal UUID
                        }

                        backend.create_queue_message(
                            QueueMessageCreate(
                                type=QueueMessageType.get_or_create(
                                    "dao_proposal_evaluation"
                                ),
                                message=message_data,
                                dao_id=dao_data["id"],
                                wallet_id=wallet_id,
                            )
                        )

                    self.logger.info(
                        f"Created {len(selected_wallet_ids)} evaluation queue messages for proposal {proposal.id}"
                    )
                else:
                    self.logger.warning(
                        f"No agents found holding tokens for DAO {dao_data['id']} - skipping lottery entirely"
                    )
            except Exception as e:
                self.logger.error(f"Error creating proposal in database: {str(e)}")
                raise
        else:
            # Update existing proposal with new data from chainhook
            existing_proposal = existing_proposals[0]
            self.logger.info(
                f"Updating existing action proposal in database: {existing_proposal.id}"
            )

            try:
                # First try to decode parameters as hex
                decoded_parameters = decode_hex_parameters(proposal_info["parameters"])

                # Sanitize the decoded parameters to remove null bytes and invalid characters
                if decoded_parameters is not None:
                    parameters = self._sanitize_string(decoded_parameters)
                    self.logger.debug(
                        f"Decoded and sanitized parameters: {parameters[:100]}..."
                    )
                else:
                    parameters = proposal_info["parameters"]
                    self.logger.debug("Using original parameters (hex decoding failed)")

                # Parse title/tags from content and generate summary using AI
                proposal_id_str = str(proposal_info.get("proposal_id", "updated"))
                metadata = await self._parse_and_generate_proposal_metadata(
                    parameters, dao_data["name"], proposal_id_str
                )

                # Determine contract status based on transaction success
                contract_status = (
                    ContractStatus.DEPLOYED if tx_success else ContractStatus.FAILED
                )

                # Prepare update data with new information from chainhook
                update_data = ProposalBase(
                    title=metadata["title"],
                    content=parameters,
                    summary=metadata["summary"],
                    status=contract_status,
                    # Update fields from payload
                    action=proposal_info["action"],
                    caller=proposal_info["caller"],
                    creator=proposal_info["creator"],
                    proposal_id=proposal_info["proposal_id"],
                    liquid_tokens=proposal_info["liquid_tokens"],
                    bond=proposal_info["bond"],
                    # Fields from updated payload
                    contract_caller=proposal_info["contract_caller"],
                    created_btc=proposal_info["created_btc"],
                    created_stx=proposal_info["created_stx"],
                    creator_user_id=proposal_info["creator_user_id"],
                    exec_end=proposal_info["exec_end"],
                    exec_start=proposal_info["exec_start"],
                    memo=proposal_info["memo"],
                    tx_sender=proposal_info["tx_sender"],
                    vote_end=proposal_info["vote_end"],
                    vote_start=proposal_info["vote_start"],
                    voting_delay=proposal_info["voting_delay"],
                    voting_period=proposal_info["voting_period"],
                    voting_quorum=proposal_info["voting_quorum"],
                    voting_reward=proposal_info["voting_reward"],
                    voting_threshold=proposal_info["voting_threshold"],
                )

                # Update the existing proposal
                updated_proposal = backend.update_proposal(
                    existing_proposal.id, update_data
                )

                self.logger.info(
                    f"Successfully updated action proposal {updated_proposal.id} with chainhook data"
                )

                # Create Twitter post for successful proposal updates (when blockchain data is added)
                if tx_success:
                    # Create Twitter post for updated proposal submission
                    proposal_url = (
                        f"{config.api.base_url}/proposals/{updated_proposal.id}"
                    )
                    follow_up_message = f"\nView contribution details:\n{proposal_url}"

                    # Create the first post for proposal submission
                    first_post = f"📥 Submitted: Contribution #{updated_proposal.proposal_id} (testnet)\n🤖 Agent Voting Begins: Block {updated_proposal.vote_start:,} "

                    # Add x_url if available
                    if updated_proposal.x_url:
                        first_post += f"\n{updated_proposal.x_url}"

                    # Create the posts array
                    posts = [first_post, follow_up_message]

                    # Create queue message for Twitter
                    tweet_message = backend.create_queue_message(
                        QueueMessageCreate(
                            type=QueueMessageType.get_or_create("tweet"),
                            message={
                                "posts": posts,
                            },
                            dao_id=dao_data["id"],
                        )
                    )
                    self.logger.info(
                        f"Created tweet queue message for updated proposal submission: {tweet_message.id}"
                    )

                # Queue evaluation messages for proposals with agents
                # Note: Removing tx_success check to debug lottery creation issues
                self.logger.info(
                    f"Starting lottery process for updated proposal {updated_proposal.id} (tx_success: {tx_success})"
                )

                # Check if lottery has already been conducted for this proposal
                existing_lottery = backend.get_lottery_result_by_proposal(
                    updated_proposal.id
                )

                if not existing_lottery:
                    # Conduct new quorum-aware lottery if none exists
                    agents = self._get_agent_token_holders(dao_data["id"])
                    if agents:
                        lottery_selection = LotterySelection()
                        self.logger.info(
                            f"Update path - Bitcoin block hash available: {bool(bitcoin_block_hash)}"
                        )
                        self.logger.info(
                            f"Update path - Proposal liquid tokens: {updated_proposal.liquid_tokens}"
                        )

                        if bitcoin_block_hash and updated_proposal.liquid_tokens:
                            self.logger.info(
                                "Update path - Conditions met for full lottery"
                            )
                            lottery_selection = self._conduct_quorum_lottery(
                                agents,
                                updated_proposal.liquid_tokens,
                                bitcoin_block_hash,
                                bitcoin_block_height or 0,
                            )

                            # Record the lottery results
                            try:
                                self.logger.info(
                                    "Update path - Attempting to create lottery result"
                                )
                                lottery_result = backend.create_lottery_result(
                                    LotteryResultCreate(
                                        proposal_id=updated_proposal.id,
                                        dao_id=dao_data["id"],
                                        bitcoin_block_height=bitcoin_block_height,
                                        bitcoin_block_hash=bitcoin_block_hash,
                                        lottery_seed=hashlib.sha256(
                                            bitcoin_block_hash.encode()
                                        ).hexdigest(),
                                        selected_wallets=lottery_selection.selected_wallets,
                                        liquid_tokens_at_creation=lottery_selection.liquid_tokens_at_creation,
                                        quorum_threshold=lottery_selection.quorum_threshold,
                                        total_selected_tokens=lottery_selection.total_selected_tokens,
                                        quorum_achieved=lottery_selection.quorum_achieved,
                                        quorum_percentage=lottery_selection.quorum_percentage,
                                        total_eligible_wallets=lottery_selection.total_eligible_wallets,
                                        total_eligible_tokens=lottery_selection.total_eligible_tokens,
                                        selection_rounds=lottery_selection.selection_rounds,
                                        # Backward compatibility
                                        selected_wallet_ids=extract_wallet_ids_from_selection(
                                            lottery_selection.selected_wallets
                                        ),
                                    )
                                )
                                self.logger.info(
                                    f"Update path - Successfully created lottery result with ID: {lottery_result.id}"
                                )
                            except Exception as update_lottery_error:
                                self.logger.error(
                                    f"Update path - Failed to create lottery result: {str(update_lottery_error)}"
                                )
                                raise

                            self.logger.info(
                                f"Quorum lottery completed for updated proposal {updated_proposal.id}: "
                                f"selected {len(lottery_selection.selected_wallets)} agents "
                                f"({'✓' if lottery_selection.quorum_achieved else '✗'} quorum achieved)"
                            )
                        else:
                            # Fallback: use old system if no Bitcoin block hash or liquid tokens
                            self.logger.warning("Update path - Using fallback lottery")
                            fallback_bitcoin_height = bitcoin_block_height or 0
                            try:
                                lottery_result = self._create_fallback_lottery_result(
                                    updated_proposal,
                                    dao_data["id"],
                                    agents,
                                    fallback_bitcoin_height,
                                    bitcoin_block_hash,
                                    lottery_selection,
                                    is_update=True,
                                )
                                self.logger.info(
                                    f"Update path - Successfully created fallback lottery result with ID: {lottery_result.id}"
                                )
                            except Exception as fallback_error:
                                self.logger.error(
                                    f"Update path fallback lottery failed for proposal {updated_proposal.id}, dao {dao_data['id']}: {str(fallback_error)}"
                                )
                                raise

                        # Create evaluation queue messages for selected agents only
                        selected_wallet_ids = extract_wallet_ids_from_selection(
                            lottery_selection.selected_wallets
                        )
                        for wallet_id in selected_wallet_ids:
                            message_data = {
                                "proposal_id": updated_proposal.id,  # Only pass the proposal UUID
                            }

                            backend.create_queue_message(
                                QueueMessageCreate(
                                    type=QueueMessageType.get_or_create(
                                        "dao_proposal_evaluation"
                                    ),
                                    message=message_data,
                                    dao_id=dao_data["id"],
                                    wallet_id=wallet_id,
                                )
                            )

                        self.logger.info(
                            f"Created {len(selected_wallet_ids)} evaluation queue messages for updated proposal {updated_proposal.id}"
                        )
                    else:
                        self.logger.warning(
                            f"Update path - No agents found holding tokens for DAO {dao_data['id']}"
                        )
                else:
                    self.logger.info(
                        f"Lottery already exists for proposal {updated_proposal.id}, skipping lottery selection"
                    )

            except Exception as e:
                self.logger.error(f"Error updating proposal in database: {str(e)}")
                raise
