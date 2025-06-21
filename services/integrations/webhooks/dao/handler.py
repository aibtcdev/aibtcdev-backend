"""Handler for DAO webhook payloads."""

from typing import Any, Dict, List
from uuid import UUID

from backend.factory import backend
from backend.models import (
    ContractStatus,
    DAOCreate,
    ExtensionCreate,
    TokenCreate,
    XCredsCreate,
)
from config import config
from lib.logger import configure_logger
from services.integrations.webhooks.base import WebhookHandler
from services.integrations.webhooks.dao.models import (
    DAOWebhookPayload,
    DAOWebhookResponse,
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

    async def handle(self, parsed_data: DAOWebhookPayload) -> Dict[str, Any]:
        """Handle the parsed DAO webhook data.

        Args:
            parsed_data: The parsed and validated DAO webhook payload

        Returns:
            Dict containing the result of handling the webhook with created entities

        Raises:
            Exception: If there is an error creating any of the entities
        """
        try:
            self.logger.info(f"Handling DAO webhook for '{parsed_data.name}'")

            # Create the DAO
            dao_create = DAOCreate(
                name=parsed_data.name,
                mission=parsed_data.mission,
                description=parsed_data.description or parsed_data.mission,
                is_deployed=True,
                is_broadcasted=True,
            )

            dao = self.db.create_dao(dao_create)
            self.logger.info(f"Created DAO with ID: {dao.id}")

            # Create X credentials for the DAO
            new_cred = XCredsCreate(
                dao_id=dao.id,
                consumer_key=config.twitter.default_consumer_key,
                consumer_secret=config.twitter.default_consumer_secret,
                client_id=config.twitter.default_client_id,
                client_secret=config.twitter.default_client_secret,
                access_token=config.twitter.default_access_token,
                access_secret=config.twitter.default_access_secret,
                username=config.twitter.default_username,
                bearer_token=config.twitter.default_bearer_token,
            )

            x_creds = self.db.create_x_creds(new_cred)
            self.logger.info(f"Created X credentials with ID: {x_creds.id}")

            # Find the main DAO token contract
            dao_token_contract = None
            for contract in parsed_data.contracts:
                if contract.type.value == "TOKEN" and contract.subtype == "DAO":
                    dao_token_contract = contract
                    break

            if not dao_token_contract:
                raise ValueError("No DAO token contract found in contracts list")

            # Create the main DAO token
            token_create = TokenCreate(
                dao_id=dao.id,
                contract_principal=dao_token_contract.contract_principal,
                tx_id=dao_token_contract.tx_id,
                name=parsed_data.name,  # Use DAO name as token name
                description=parsed_data.description or parsed_data.mission,
                symbol=parsed_data.token_info.symbol,
                decimals=parsed_data.token_info.decimals,
                max_supply=parsed_data.token_info.max_supply,
                uri=parsed_data.token_info.uri,
                image_url=parsed_data.token_info.image_url,
                x_url=parsed_data.token_info.x_url,
                telegram_url=parsed_data.token_info.telegram_url,
                website_url=parsed_data.token_info.website_url,
                status=ContractStatus.DEPLOYED,
            )

            token = self.db.create_token(token_create)
            self.logger.info(f"Created token with ID: {token.id}")

            # Create extensions for DAO extension contracts
            extension_ids: List[UUID] = []
            for contract in parsed_data.contracts:
                extension_create = ExtensionCreate(
                    dao_id=dao.id,
                    type=contract.type.value,
                    subtype=contract.subtype,
                    contract_principal=contract.contract_principal,
                    tx_id=contract.tx_id,
                    status=ContractStatus.DEPLOYED,
                )

                extension = self.db.create_extension(extension_create)
                extension_ids.append(extension.id)
                self.logger.info(
                    f"Created extension with ID: {extension.id} for type: {contract.type.value} and subtype: {contract.subtype}"
                )

            # Prepare response
            response = DAOWebhookResponse(
                dao_id=dao.id,
                extension_ids=extension_ids if extension_ids else None,
                token_id=token.id,
            )

            return {
                "success": True,
                "message": f"Successfully created DAO '{dao.name}' with ID: {dao.id}",
                "data": response.model_dump(),
            }

        except Exception as e:
            self.logger.error(f"Error handling DAO webhook: {str(e)}", exc_info=True)
            raise
