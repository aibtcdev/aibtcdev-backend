"""Handler for DAO webhook payloads."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import ContractStatus, DAOCreate, ExtensionCreate, TokenCreate
from lib.logger import configure_logger
from services.webhooks.base import WebhookHandler
from services.webhooks.dao.models import (
    AIBTCCoreWebhookPayload,  # Changed from DAOWebhookPayload
    AIBTCCoreRequestContract,  # For type hinting if needed, though direct use is in parsed_data
    DAOWebhookResponse,
    ContractType,
    TokenSubtype,
)


class DAOHandler(WebhookHandler):
    """Handler for DAO webhook payloads.

    This handler processes validated DAO webhook payloads and creates
    the corresponding DAO, extensions, and token in the database.
    """

    def __init__(self):
        """Initialize the DAO webhook handler."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)
        self.db = backend

    async def handle(self, parsed_data: AIBTCCoreWebhookPayload) -> Dict[str, Any]:
        """Handle the parsed AIBTCCoreWebhookPayload data.

        Args:
            parsed_data: The parsed and validated AIBTCCoreWebhookPayload

        Returns:
            Dict containing the result of handling the webhook with created entities

        Raises:
            Exception: If there is an error creating any of the entities
        """
        try:
            self.logger.info(
                f"Handling DAO webhook (new structure) for '{parsed_data.name}'"
            )

            # Create the DAO
            dao_create = DAOCreate(
                name=parsed_data.name,
                mission=parsed_data.mission,
                description=parsed_data.mission,  # Use mission for description
                is_deployed=True,
                is_broadcasted=True,
            )
            dao = self.db.create_dao(dao_create)
            self.logger.info(f"Created DAO with ID: {dao.id}")

            extension_ids: List[UUID] = []
            token_contract_entry: Optional[AIBTCCoreRequestContract] = None

            for contract_item in parsed_data.contracts:
                # Identify the main token contract from the list
                # This condition might need to be more specific based on your contract naming or type/subtype conventions
                if (
                    contract_item.type == ContractType.TOKEN
                    and contract_item.subtype == TokenSubtype.DAO
                ):
                    if token_contract_entry is not None:
                        # Handle case where multiple token contracts are unexpectedly found
                        self.logger.warning(
                            f"Multiple token contracts found for DAO '{parsed_data.name}'. Using the first one found."
                        )
                        # Or raise an error: raise ValueError("Multiple token contracts found")
                    token_contract_entry = contract_item
                    continue  # Don't process the token as a generic extension here

                # Create extensions for other contracts
                # The 'deployer' (contract_item.deployer) is available here but not passed to ExtensionCreate
                extension_create = ExtensionCreate(
                    dao_id=dao.id,
                    type=contract_item.type,
                    subtype=contract_item.subtype,
                    contract_principal=contract_item.contract_principal,
                    tx_id=contract_item.tx_id,
                    status=ContractStatus.DEPLOYED,  # Assuming DEPLOYED as tx_id is present
                )
                extension = self.db.create_extension(extension_create)
                extension_ids.append(extension.id)
                self.logger.info(
                    f"Created extension with ID: {extension.id} for type: {contract_item.type} and subtype: {contract_item.subtype}"
                )

            if token_contract_entry is None:
                self.logger.error(
                    f"Token contract entry not found in contracts list for DAO '{parsed_data.name}'"
                )
                raise ValueError("Token contract entry not found in contracts list")

            # Create token
            # The 'deployer' (token_contract_entry.deployer) is available here but not passed to TokenCreate
            token_create = TokenCreate(
                dao_id=dao.id,
                contract_principal=token_contract_entry.contract_principal,
                tx_id=token_contract_entry.tx_id,
                name=parsed_data.token_info.symbol,  # Use symbol from token_info as name
                description=parsed_data.mission,  # Use mission for description
                symbol=parsed_data.token_info.symbol,
                decimals=parsed_data.token_info.decimals,
                max_supply=parsed_data.token_info.max_supply,
                uri=parsed_data.token_info.uri,
                image_url=parsed_data.token_info.image_url,
                x_url=parsed_data.token_info.x_url,
                telegram_url=parsed_data.token_info.telegram_url,
                website_url=parsed_data.token_info.website_url,
                status=ContractStatus.DEPLOYED,  # Assuming DEPLOYED
            )
            token = self.db.create_token(token_create)
            self.logger.info(f"Created token with ID: {token.id}")

            # Prepare response
            response = DAOWebhookResponse(
                dao_id=dao.id,
                extension_ids=extension_ids if extension_ids else None,
                token_id=token.id,
            )
            return {
                "success": True,
                "message": f"Successfully created DAO '{dao.name}' with ID: {dao.id} using new structure",
                "data": response.model_dump(),
            }

        except Exception as e:
            self.logger.error(
                f"Error handling DAO webhook (new structure): {str(e)}", exc_info=True
            )
            raise
