"""Chainhook webhook implementation."""

from .base import WebhookHandler, WebhookParser, WebhookService
from backend.factory import backend
from backend.models import (
    ContractStatus,
    ExtensionBase,
    ExtensionFilter,
    ProposalBase,
    ProposalFilter,
    TokenBase,
    TokenFilter,
)
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class TransactionIdentifier:
    hash: str


@dataclass
class TransactionWithReceipt:
    transaction_identifier: TransactionIdentifier


@dataclass
class Apply:
    transactions: List[TransactionWithReceipt]


@dataclass
class ChainHookInner:
    apply: List[Apply]


@dataclass
class ChainHookData:
    chainhook: ChainHookInner


class ChainhookParser(WebhookParser):
    """Parser for Chainhook webhook payloads."""

    def parse(self, raw_data: Dict[str, Any]) -> ChainHookData:
        """Parse Chainhook webhook data."""
        return ChainHookData(**raw_data)


class ChainhookHandler(WebhookHandler):
    """Handler for Chainhook webhook events."""

    async def handle(self, parsed_data: ChainHookData) -> Dict[str, Any]:
        """Handle Chainhook webhook data."""
        try:
            self.logger.info(
                f"Processing chainhook webhook with {len(parsed_data.chainhook.apply)} apply blocks"
            )

            non_processed_extensions = backend.list_extensions(
                filters=ExtensionFilter(
                    status=ContractStatus.PENDING,
                )
            )
            non_processed_tokens = backend.list_tokens(
                filters=TokenFilter(
                    status=ContractStatus.PENDING,
                )
            )
            non_processed_proposals = backend.list_proposals(
                filters=ProposalFilter(
                    status=ContractStatus.PENDING,
                )
            )

            self.logger.info(
                f"Found {len(non_processed_extensions)} pending extensions, "
                f"{len(non_processed_tokens)} pending tokens, "
                f"{len(non_processed_proposals)} pending proposals"
            )

            for apply in parsed_data.chainhook.apply:
                for transaction in apply.transactions:
                    tx_id = transaction.transaction_identifier.hash
                    self.logger.info(f"Processing transaction {tx_id}")

                    for extension in non_processed_extensions:
                        if extension.tx_id == tx_id:
                            self.logger.info(
                                f"Updating extension {extension.id} from {extension.status} to {ContractStatus.DEPLOYED}"
                            )
                            extension.status = ContractStatus.DEPLOYED
                            backend.update_extension(
                                extension.id,
                                update_data=ExtensionBase(
                                    status=ContractStatus.DEPLOYED
                                ),
                            )

                    for token in non_processed_tokens:
                        if token.tx_id == tx_id:
                            self.logger.info(
                                f"Updating token {token.id} from {token.status} to {ContractStatus.DEPLOYED}"
                            )
                            token.status = ContractStatus.DEPLOYED
                            backend.update_token(
                                token.id,
                                update_data=TokenBase(status=ContractStatus.DEPLOYED),
                            )

                    for proposal in non_processed_proposals:
                        if proposal.tx_id == tx_id:
                            self.logger.info(
                                f"Updating proposal {proposal.id} from {proposal.status} to {ContractStatus.DEPLOYED}"
                            )
                            proposal.status = ContractStatus.DEPLOYED
                            backend.update_proposal(
                                proposal.id,
                                update_data=ProposalBase(
                                    status=ContractStatus.DEPLOYED
                                ),
                            )

            self.logger.info("Finished processing all transactions in webhook")
            return {
                "success": True,
                "message": "Successfully processed webhook",
            }

        except Exception as e:
            self.logger.error(
                f"Error handling chainhook webhook: {str(e)}", exc_info=True
            )
            raise


class ChainhookService(WebhookService):
    """Service for handling Chainhook webhooks."""

    def __init__(self):
        super().__init__(parser=ChainhookParser(), handler=ChainhookHandler())
