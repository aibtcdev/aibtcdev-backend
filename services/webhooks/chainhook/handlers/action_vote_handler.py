"""Handler for capturing DAO action proposal votes."""

from typing import Dict, Optional

from backend.factory import backend
from backend.models import ProposalFilter, ProposalType
from services.webhooks.chainhook.handlers.base_vote_handler import BaseVoteHandler
from services.webhooks.chainhook.models import Event


class ActionVoteHandler(BaseVoteHandler):
    """Handler for capturing and processing DAO action proposal votes.

    This handler identifies contract calls related to voting on action proposals
    and updates vote records in the database.
    """

    def _find_proposal(
        self, contract_identifier: str, proposal_identifier: int
    ) -> Optional[Dict]:
        """Find the action proposal in the database.

        Args:
            contract_identifier: The contract identifier
            proposal_identifier: The on-chain proposal ID

        Returns:
            Optional[Dict]: The proposal data if found, None otherwise
        """
        proposals = backend.list_proposals(
            filters=ProposalFilter(
                contract_principal=contract_identifier,
                proposal_id=proposal_identifier,
                type=ProposalType.ACTION,
            )
        )

        if not proposals:
            self.logger.warning(
                f"No action proposal found for ID {proposal_identifier} in {contract_identifier}"
            )
            return None

        return proposals[0]

    def _get_vote_info_from_events(self, events: list[Event]) -> Optional[Dict]:
        """Extract the action vote information from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing vote information if found, None otherwise
        """
        for event in events:
            # Find print events with vote information
            if (
                event.type == "SmartContractEvent"
                and hasattr(event, "data")
                and event.data.get("topic") == "print"
            ):
                event_data = event.data
                value = event_data.get("value", {})

                # Check for the new notification format
                notification = value.get("notification", "")
                if "vote-on-action-proposal" in notification:
                    payload = value.get("payload", {})
                    if not payload:
                        self.logger.warning("Empty payload in vote event")
                        return None

                    return {
                        "proposal_identifier": payload.get(
                            "proposalId"
                        ),  # Numeric ID for action proposals
                        "voter": payload.get("voter"),
                        "caller": payload.get("contractCaller"),  # Updated field name
                        "tx_sender": payload.get("txSender"),  # New field
                        "amount": payload.get("amount"),
                        "vote_value": payload.get(
                            "vote"
                        ),  # Vote value is now directly in payload
                        "voter_user_id": payload.get("voterUserId"),  # New field
                    }

        self.logger.warning("Could not find vote information in transaction events")
        return None
