"""Handler for capturing action proposal conclusions and updating proposal records."""

from typing import Dict, List, Optional


from app.backend.factory import backend
from app.backend.models import (
    ExtensionFilter,
    ProposalBase,
    ProposalFilter,
    QueueMessageCreate,
    QueueMessageType,
)
from app.config import config
from app.lib.utils import strip_metadata_section
from app.services.integrations.webhooks.chainhook.handlers.base import (
    ChainhookEventHandler,
)
from app.services.integrations.webhooks.chainhook.models import (
    Event,
    TransactionWithReceipt,
)


class ActionConcluderHandler(ChainhookEventHandler):
    """Handler for capturing and processing action proposal conclusions.

    This handler identifies contract calls with conclude-action-proposal method and:
    1. Updates proposal records with conclusion data from the blockchain
    2. Creates appropriate queue messages for further processing (tweets, etc.)
    """

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with conclude-action-proposal method.

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

        # Check if the method name is exactly "conclude-action-proposal"
        tx_method = tx_data_content.get("method", "")
        is_conclude_proposal = tx_method == "conclude-action-proposal"

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        if is_conclude_proposal and tx_success:
            self.logger.debug(f"Found conclude-action-proposal method: {tx_method}")

        return (
            tx_kind_type == "ContractCall"
            and is_conclude_proposal
            and tx_success is True
        )

    def _find_dao_for_contract(self, contract_identifier: str) -> Optional[Dict]:
        """Find the DAO associated with the given contract.

        Args:
            contract_identifier: The contract identifier to search for

        Returns:
            Optional[Dict]: The DAO data if found, None otherwise
        """
        # Find extensions with this contract principal
        extensions = backend.list_extensions(
            filters=ExtensionFilter(
                contract_principal=contract_identifier,
            )
        )

        if not extensions:
            self.logger.warning(
                f"No extensions found for contract {contract_identifier}"
            )
            return None

        # Get the DAO for the first matching extension
        dao_id = extensions[0].dao_id
        if not dao_id:
            self.logger.warning("Extension found but no DAO ID associated with it")
            return None

        dao = backend.get_dao(dao_id)
        if not dao:
            self.logger.warning(f"No DAO found with ID {dao_id}")
            return None

        self.logger.info(f"Found DAO for contract {contract_identifier}: {dao.name}")
        return dao.model_dump()

    def _get_proposal_conclusion_data(self, events: List[Event]) -> Optional[Dict]:
        """Extract proposal conclusion data from action-proposal-voting contract events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: The proposal conclusion data if found, None otherwise
        """
        for event in events:
            # Find print events from action-proposal-voting contract
            if (
                event.type == "SmartContractEvent"
                and hasattr(event, "data")
                and event.data.get("topic") == "print"
                and "action-proposal-voting"
                in event.data.get("contract_identifier", "")
            ):
                value = event.data.get("value")

                # Handle structured format with payload
                if isinstance(value, dict):
                    notification = value.get("notification", "")
                    if "conclude-action-proposal" in notification:
                        payload = value.get("payload", {})
                        if isinstance(payload, dict):
                            return payload

        self.logger.warning(
            "Could not find proposal conclusion data in transaction events"
        )
        return None

    def _update_proposal_record(
        self, dao_data: Dict, conclusion_data: Dict
    ) -> Optional[Dict]:
        """Update proposal record with conclusion data.

        Args:
            dao_data: The DAO data
            conclusion_data: The conclusion data from the blockchain

        Returns:
            Optional[Dict]: The updated proposal if found and updated, None otherwise
        """
        proposal_id = conclusion_data.get("proposalId")
        if proposal_id is None:
            self.logger.warning("No proposal ID found in conclusion data")
            return None

        # Find the proposal by DAO and proposal ID
        proposals = backend.list_proposals(
            filters=ProposalFilter(
                dao_id=dao_data["id"],
                proposal_id=proposal_id,
            )
        )

        if not proposals:
            self.logger.warning(
                f"No proposal found with ID {proposal_id} for DAO {dao_data['name']}"
            )
            return None

        proposal = proposals[0]

        # Update proposal with conclusion data
        update_data = ProposalBase(
            executed=conclusion_data.get("executed"),
            passed=conclusion_data.get("passed"),
            met_quorum=conclusion_data.get("metQuorum"),
            met_threshold=conclusion_data.get("metThreshold"),
            votes_for=str(conclusion_data.get("votesFor", 0)),
            votes_against=str(conclusion_data.get("votesAgainst", 0)),
            liquid_tokens=str(conclusion_data.get("liquidTokens", 0)),
            bond=str(conclusion_data.get("bond", 0)),
            concluded_by=conclusion_data.get("txSender"),
            creator=conclusion_data.get("creator"),
        )

        self.logger.info(
            f"Updating proposal {proposal_id} for DAO {dao_data['name']} with conclusion data"
        )

        updated_proposal = backend.update_proposal(proposal.id, update_data)
        return updated_proposal.model_dump() if updated_proposal else None

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle action proposal conclusion transactions.

        Processes contract call transactions that conclude action proposals:
        1. Updates proposal records with conclusion data from the blockchain
        2. Creates queue messages for tweets with the onchain message content
        3. Associates them with the appropriate DAO

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
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

        # Get the events from the transaction
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []

        # Extract proposal conclusion data and update the proposal record
        conclusion_data = self._get_proposal_conclusion_data(events)
        if not conclusion_data:
            self.logger.warning(
                "No proposal conclusion data found in transaction events"
            )
            return

        updated_proposal = self._update_proposal_record(dao_data, conclusion_data)
        if not updated_proposal:
            self.logger.warning(
                f"Failed to update proposal {conclusion_data.get('proposalId')} "
                f"for DAO {dao_data['name']}"
            )
            return

        self.logger.info(
            f"Successfully updated proposal {conclusion_data.get('proposalId')} "
            f"for DAO {dao_data['name']}"
        )

        # Look up the full proposal record to get the content field
        proposal_id = conclusion_data.get("proposalId")
        proposals = backend.list_proposals(
            filters=ProposalFilter(
                dao_id=dao_data["id"],
                proposal_id=proposal_id,
            )
        )

        if not proposals:
            self.logger.warning(
                f"Could not find proposal {proposal_id} for content lookup"
            )
            return

        proposal = proposals[0]
        message = proposal.content
        if not message:
            self.logger.warning("No content found in the proposal")
            return

        # Clean the message content by removing metadata section
        clean_message = strip_metadata_section(message)

        self.logger.info(
            f"Processing concluded proposal message from DAO {dao_data['name']}: {clean_message[:100]}..."
        )

        # Check if proposal passed and create appropriate queue messages
        proposal_passed = proposal.passed or False

        if proposal_passed:
            # Get DAO information to include the name in the post
            dao = backend.get_dao(proposal.dao_id) if proposal.dao_id else None
            dao_name = dao.name if dao else ""

            # Set reward amount based on DAO name
            if dao_name == "AIBTC":
                reward_amount = "$10 BTC"
            elif dao_name == "ELONBTC":
                reward_amount = "$50 BTC"
            elif dao_name:
                reward_amount = f"1,000 ${dao_name}"
            else:
                reward_amount = "1,000 $FACES"

            # Create the new post format for approved proposals
            proposal_url = f"{config.api.base_url}/proposals/{proposal.id}"
            follow_up_message = f"View contribution details: {proposal_url}"

            # Create the first post with the approved contribution format
            first_post = f"✅ Approved: Contribution #{proposal.proposal_id} {dao_name} (testnet)\n💰 Reward: {reward_amount}"

            # Add x_url if available (will be implemented soon)
            if proposal.x_url:
                first_post += f"\n{proposal.x_url}"

            # Create the posts array with the new format
            posts = [first_post, follow_up_message]

            # Create queue message for Twitter with new "posts" format
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
                f"Created tweet queue message with {len(posts)} posts (new approved format): {tweet_message.id}"
            )

            # Calculate participation and approval percentages for passed proposal
            votes_for = int(proposal.votes_for or 0)
            votes_against = int(proposal.votes_against or 0)
            total_votes = votes_for + votes_against

            participation_pct = 0.0
            approval_pct = 0.0

            if total_votes > 0:
                # For participation, we'd need total eligible voters - using liquid_tokens as proxy
                liquid_tokens = int(proposal.liquid_tokens or 0)
                if liquid_tokens > 0:
                    participation_pct = (total_votes / liquid_tokens) * 100

                # Approval percentage is votes_for / total_votes
                approval_pct = (votes_for / total_votes) * 100

            # Format the Discord message with new structured format for passed proposal
            formatted_message = "\n=======================================\n\n"
            formatted_message += f"✅ Approved: Contribution #{proposal.proposal_id}\n"
            # Set reward amount based on DAO name for Discord
            if dao_name == "AIBTC":
                discord_reward = "💰 Reward: $10 BTC"
            if dao_name == "ELONBTC":
                discord_reward = "💰 Reward: $50 BTC"
            elif dao_name:
                discord_reward = f"⭐️ Reward: 1,000 ${dao_name}"
            else:
                discord_reward = "⭐️ Reward: 1,000 $FACES"
            formatted_message += f"{discord_reward}\n\n"

            # Add URL section if x_url is available
            if proposal.x_url:
                formatted_message += f"URL: {proposal.x_url}\n"

            # Add details link
            proposal_url = f"{config.api.base_url}/proposals/{proposal.id}"
            formatted_message += f"Details: {proposal_url}\n\n"

            formatted_message += f"Participation: {participation_pct:.1f}%\n"
            formatted_message += f"Approval: {approval_pct:.1f}%\n\n"
            formatted_message += "======================================="

            discord_message = backend.create_queue_message(
                QueueMessageCreate(
                    type=QueueMessageType.get_or_create("discord"),
                    message={"content": formatted_message, "proposal_status": "passed"},
                    dao_id=dao_data["id"],
                )
            )
            self.logger.info(
                f"Created Discord queue message (proposal passed): {discord_message.id}"
            )
        else:
            # For failed proposals, create only Discord message (no Twitter)

            # Calculate participation and approval percentages
            votes_for = int(proposal.votes_for or 0)
            votes_against = int(proposal.votes_against or 0)
            total_votes = votes_for + votes_against

            participation_pct = 0.0
            approval_pct = 0.0

            if total_votes > 0:
                # For participation, we'd need total eligible voters - using liquid_tokens as proxy
                liquid_tokens = int(proposal.liquid_tokens or 0)
                if liquid_tokens > 0:
                    participation_pct = (total_votes / liquid_tokens) * 100

                # Approval percentage is votes_for / total_votes
                approval_pct = (votes_for / total_votes) * 100

            # Format the Discord message with new structured format for failed proposal
            formatted_message = "\n=======================================\n\n"
            formatted_message += f"🛑 Rejected: Contribution #{proposal.proposal_id}\n"

            # Add URL section if x_url is available
            if proposal.x_url:
                formatted_message += f"URL: {proposal.x_url}\n"

            # Add details link
            proposal_url = f"{config.api.base_url}/proposals/{proposal.id}"
            formatted_message += f"Details: {proposal_url}\n\n"

            formatted_message += f"Participation: {participation_pct:.1f}%\n"
            formatted_message += f"Approval: {approval_pct:.1f}%\n\n"
            formatted_message += "======================================="

            discord_message = backend.create_queue_message(
                QueueMessageCreate(
                    type=QueueMessageType.get_or_create("discord"),
                    message={"content": formatted_message, "proposal_status": "failed"},
                    dao_id=dao_data["id"],
                )
            )
            self.logger.info(
                f"Created Discord queue message (proposal failed): {discord_message.id}"
            )
