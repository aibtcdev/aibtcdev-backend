"""Handler for DAO webhook payloads."""

from typing import Any, Dict, List
from uuid import UUID

from backend.factory import backend
from backend.models import DAOCreate, ExtensionCreate, TokenCreate
from lib.logger import configure_logger
from services.webhooks.base import WebhookHandler
from services.webhooks.dao.models import DAOWebhookPayload, DAOWebhookResponse


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
                description=parsed_data.description,
            )

            dao = self.db.create_dao(dao_create)
            self.logger.info(f"Created DAO with ID: {dao.id}")

            # Create extensions if provided
            extension_ids: List[UUID] = []
            if parsed_data.extensions:
                for ext_data in parsed_data.extensions:
                    extension_create = ExtensionCreate(
                        dao_id=dao.id,
                        type=ext_data.type,
                        contract_principal=ext_data.contract_principal,
                        tx_id=ext_data.tx_id,
                    )

                    extension = self.db.create_extension(extension_create)
                    extension_ids.append(extension.id)
                    self.logger.info(f"Created extension with ID: {extension.id}")

            # Create token if provided
            token_id = None
            if parsed_data.token:
                token_create = TokenCreate(
                    dao_id=dao.id,
                    contract_principal=parsed_data.token.contract_principal,
                    tx_id=parsed_data.token.tx_id,
                    name=parsed_data.token.name,
                    description=parsed_data.token.description,
                    symbol=parsed_data.token.symbol,
                    decimals=parsed_data.token.decimals,
                    max_supply=parsed_data.token.max_supply,
                    uri=parsed_data.token.uri,
                    image_url=parsed_data.token.image_url,
                    x_url=parsed_data.token.x_url,
                    telegram_url=parsed_data.token.telegram_url,
                    website_url=parsed_data.token.website_url,
                )

                token = self.db.create_token(token_create)
                token_id = token.id
                self.logger.info(f"Created token with ID: {token.id}")

            # Prepare response
            response = DAOWebhookResponse(
                dao_id=dao.id,
                extension_ids=extension_ids if extension_ids else None,
                token_id=token_id,
            )

            return {
                "success": True,
                "message": f"Successfully created DAO '{dao.name}' with ID: {dao.id}",
                "data": response.model_dump(),
            }

        except Exception as e:
            self.logger.error(f"Error handling DAO webhook: {str(e)}", exc_info=True)
            raise
