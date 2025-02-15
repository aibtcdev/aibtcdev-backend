"""Chainhook webhook implementation."""
import json

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
    QueueMessageCreate,
)
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class TransactionIdentifier:
    hash: str


@dataclass
class TransactionWithReceipt:
    transaction_identifier: TransactionIdentifier
    metadata: Dict[str, Any]  # Added to access transaction metadata
    operations: List[Dict[str, Any]]  # Added to include the operations field


@dataclass
class BlockIdentifier:
    hash: str
    index: int


@dataclass
class Apply:
    block_identifier: BlockIdentifier
    transactions: List[TransactionWithReceipt]
    # Add other fields if necessary


@dataclass
class ChainHookData:
    apply: List[Apply]  # Ensure this matches the structure of your incoming data


class ChainhookParser(WebhookParser):
    """Parser for Chainhook webhook payloads."""

    def parse(self, raw_data: Dict[str, Any]) -> ChainHookData:
        """Parse Chainhook webhook data."""
        return ChainHookData(
            apply=[
                Apply(
                    block_identifier=BlockIdentifier(**apply_data['block_identifier']),
                    transactions=[
                        TransactionWithReceipt(
                            transaction_identifier=TransactionIdentifier(**tx['transaction_identifier']),
                            metadata=tx['metadata'],
                            operations=tx.get('operations', [])  # Ensure operations are included
                        )
                        for tx in apply_data.get('transactions', [])
                    ]
                )
                for apply_data in raw_data.get('apply', [])
            ]
        )


class ChainhookHandler(WebhookHandler):
    """Handler for Chainhook webhook events."""

    async def handle(self, parsed_data: ChainHookData) -> Dict[str, Any]:
        """Handle Chainhook webhook data."""
        try:
            self.logger.info(
                f"Processing chainhook webhook with {len(parsed_data.apply)} apply blocks"
            )

            # Existing logic for processing non-processed extensions, tokens, and proposals
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

            for apply in parsed_data.apply:
                for transaction in apply.transactions:
                    tx_metadata = transaction.metadata
                    tx_kind = tx_metadata.get("kind", {})
                    tx_data = tx_kind.get("data", {})
                    
                    # New logic: Check if the transaction is a contract call and matches the conditions
                    self.logger.debug(f"Transaction kind: {tx_kind}")
                    self.logger.debug(f"Transaction data: {tx_data}")
                    self.logger.debug(f"Transaction metadata: {tx_metadata}")
                    if (
                        tx_kind.get("type") == "ContractCall" and
                        tx_data.get("method") == "send" and
                        tx_metadata.get("success") is False
                    ):
                        sender = tx_metadata.get("sender")
                        args = tx_data.get("args", [0])
                        self.logger.info(f"Transaction from sender {sender} with args: {args}")
                        # Print args in a clean format
                        # print("Transaction Arguments:")
                        # for arg in args:
                        #     print(f"- {arg}")

                        extension = backend.list_extensions(
                            filters=ExtensionFilter(
                                contract_principal=tx_data.get("contract_identifier")
                            )
                    
                        )
                        if extension:
                            new_message = backend.create_queue_message(QueueMessageCreate( 
                                type="tweet",
                                message={"message": args[0]},
                                dao_id=extension[0].dao_id,
                            )
                            )
                            self.logger.info(f"New message: {new_message}")


                    # Existing logic for processing transactions
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