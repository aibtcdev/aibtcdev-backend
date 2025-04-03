"""Handler for capturing DAO core proposal votes."""

from typing import Dict, Optional

from backend.factory import backend
from backend.models import ProposalFilter, ProposalType
from services.webhooks.chainhook.handlers.base_vote_handler import BaseVoteHandler
from services.webhooks.chainhook.models import Event


class CoreVoteHandler(BaseVoteHandler):
    """Handler for capturing and processing DAO core proposal votes.

    This handler identifies contract calls related to voting on core proposals
    and updates vote records in the database.
    """

    def _find_proposal(
        self, contract_identifier: str, proposal_identifier: str
    ) -> Optional[Dict]:
        """Find the core proposal in the database.

        Args:
            contract_identifier: The contract identifier
            proposal_identifier: The contract principal of the proposal

        Returns:
            Optional[Dict]: The proposal data if found, None otherwise
        """
        proposals = backend.list_proposals(
            filters=ProposalFilter(
                contract_principal=contract_identifier,
                proposal_contract=proposal_identifier,
                type=ProposalType.CORE,
            )
        )

        if not proposals:
            self.logger.warning(
                f"No core proposal found for contract {proposal_identifier} in {contract_identifier}"
            )
            return None

        return proposals[0]

    def _get_vote_info_from_events(self, events: list[Event]) -> Optional[Dict]:
        """Extract the core vote information from transaction events.

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

                if value.get("notification") == "vote-on-proposal":
                    payload = value.get("payload", {})
                    if not payload:
                        self.logger.warning("Empty payload in vote event")
                        return None

                    return {
                        "proposal_identifier": payload.get(
                            "proposal"
                        ),  # Contract principal for core proposals
                        "voter": payload.get("voter"),
                        "caller": payload.get("caller"),
                        "amount": str(payload.get("amount")),
                        "vote_value": None,  # Will be extracted from transaction args
                    }

        self.logger.warning("Could not find vote information in transaction events")
        return None
