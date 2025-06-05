"""Handler for capturing new DAO action proposals."""

from typing import Dict, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    ContractStatus,
    ProposalCreate,
    ProposalFilter,
    ProposalType,
    QueueMessageCreate,
    QueueMessageType,
)
from lib.utils import decode_hex_parameters
from services.webhooks.chainhook.handlers.base_proposal_handler import (
    BaseProposalHandler,
)
from services.webhooks.chainhook.models import Event, TransactionWithReceipt
from services.workflows.agents import ProposalMetadataAgent


class ActionProposalHandler(BaseProposalHandler):
    """Handler for capturing and processing new DAO action proposals.

    This handler identifies contract calls related to proposing actions in DAO contracts,
    creates proposal records in the database, and tracks their lifecycle.
    """

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions related to proposing actions.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

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

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        if is_proposal_method and tx_success:
            self.logger.debug(f"Found action proposal method: {tx_method}")

        return (
            tx_kind_type == "ContractCall" and is_proposal_method and tx_success is True
        )

    def _get_proposal_info_from_events(self, events: list[Event]) -> Optional[Dict]:
        """Extract the action proposal information from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing proposal information if found, None otherwise
        """
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

            # Check if this is a proposal event - updated to handle new notification format
            notification = value.get("notification", "")
            if notification == "create-action-proposal" or notification.endswith(
                "/create-action-proposal"
            ):
                payload = value.get("payload", {})
                if not payload:
                    self.logger.warning("Empty payload in proposal event")
                    return None

                return {
                    "proposal_id": payload.get("proposalId"),
                    "action": payload.get("action"),
                    "caller": payload.get("caller"),
                    "creator": payload.get("creator"),
                    "liquid_tokens": str(payload.get("liquidTokens")),
                    "parameters": payload.get("parameters"),
                    "bond": str(payload.get("bond")),
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
                }

        self.logger.warning("Could not find proposal information in transaction events")
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

    def _get_agent_token_holders(self, dao_id: UUID) -> List[Dict]:
        """Get agents that hold tokens for the given DAO.

        Args:
            dao_id: The ID of the DAO

        Returns:
            List[Dict]: List of agents with their wallet IDs
        """
        # Use the specialized backend method for getting agents with DAO tokens
        agents_with_tokens_dto = backend.get_agents_with_dao_tokens(dao_id)

        if not agents_with_tokens_dto:
            self.logger.error(f"No agents found with tokens for DAO {dao_id}")
            return []

        # Convert DTOs to the expected format
        agents_with_tokens = [
            {"agent_id": dto.agent_id, "wallet_id": dto.wallet_id}
            for dto in agents_with_tokens_dto
        ]

        self.logger.info(
            f"Found {len(agents_with_tokens)} agents holding tokens for DAO {dao_id}"
        )

        return agents_with_tokens

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

        # Use ProposalMetadataAgent to generate summary and fill missing components
        try:
            metadata_agent = ProposalMetadataAgent()

            # Use clean content for AI processing
            proposal_content = clean_content or f"Action proposal {proposal_id}"

            state = {
                "proposal_content": proposal_content,
                "dao_name": dao_name,
                "proposal_type": "action",
            }

            # Generate metadata using AI
            ai_result = await metadata_agent.process(state)

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

        Processes new action proposal transactions and creates proposal records in the database.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Get contract identifier
        contract_identifier = tx_data_content.get("contract_identifier")
        if not contract_identifier:
            self.logger.warning("No contract identifier found in transaction data")
            return

        # Find the DAO for this contract
        dao_data = self._find_dao_for_contract(contract_identifier)
        if not dao_data:
            self.logger.warning(f"No DAO found for contract {contract_identifier}")
            return

        # Get the proposal info from the transaction events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        proposal_info = self._get_proposal_info_from_events(events)
        if proposal_info is None:
            self.logger.warning(
                "Could not determine proposal information from transaction"
            )
            return

        self.logger.info(
            f"Processing new action proposal {proposal_info['proposal_id']} for DAO {dao_data['name']} "
            f"(contract: {contract_identifier})"
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
                metadata = await self._parse_and_generate_proposal_metadata(
                    parameters, dao_data["name"], str(proposal_info["proposal_id"])
                )
                # Create a new proposal record in the database
                proposal = backend.create_proposal(
                    ProposalCreate(
                        dao_id=dao_data["id"],
                        title=metadata["title"],
                        content=parameters,
                        summary=metadata["summary"],
                        contract_principal=contract_identifier,
                        tx_id=tx_id,
                        proposal_id=proposal_info["proposal_id"],
                        status=ContractStatus.DEPLOYED,  # Since it's already on-chain
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
                    f"Created new action proposal record in database: {proposal.id}"
                )

                # Queue evaluation messages for agents holding governance tokens
                agents = self._get_agent_token_holders(dao_data["id"])
                if agents:
                    for agent in agents:
                        # Create message with only the proposal ID
                        message_data = {
                            "proposal_id": proposal.id,  # Only pass the proposal UUID
                        }

                        backend.create_queue_message(
                            QueueMessageCreate(
                                type=QueueMessageType.DAO_PROPOSAL_EVALUATION,
                                message=message_data,
                                dao_id=dao_data["id"],
                                wallet_id=agent["wallet_id"],
                            )
                        )

                        self.logger.info(
                            f"Created evaluation queue message for agent {agent['agent_id']} "
                            f"to evaluate proposal {proposal.id}"
                        )
                else:
                    self.logger.warning(
                        f"No agents found holding tokens for DAO {dao_data['id']}"
                    )
            except Exception as e:
                self.logger.error(f"Error creating proposal in database: {str(e)}")
                raise
        else:
            self.logger.info(
                f"Action proposal already exists in database: {existing_proposals[0].id}"
            )
