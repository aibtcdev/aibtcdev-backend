from typing import Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from backend.factory import backend
from backend.models import UUID, XCredsCreate
from lib.logger import configure_logger

logger = configure_logger(__name__)


class CollectXCredentialsInput(BaseModel):
    """Input schema for collecting X API credentials."""

    contract_principal: str = Field(..., description="Contract Principal")
    consumer_key: str = Field(..., description="X API Key")
    consumer_secret: str = Field(..., description="X API Secret")
    access_token: str = Field(..., description="X API Access Token")
    access_secret: str = Field(..., description="X API Access Secret")
    client_id: str = Field(..., description="OAuth 2.0 Client ID")
    client_secret: str = Field(..., description="OAuth 2.0 Client Secret")
    username: str = Field(..., description="X Username")


class CollectXCredentialsTool(BaseTool):
    name: str = "collect_x_credentials"
    description: str = (
        "Collect X (Twitter) API credentials and store them securely in the database"
    )
    args_schema: Type[BaseModel] = CollectXCredentialsInput
    return_direct: bool = True
    profile_id: Optional[UUID] = None

    def __init__(
        self,
        profile_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.profile_id = profile_id

    def _deploy(
        self,
        contract_principal: str,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_secret: str,
        client_id: str,
        client_secret: str,
        username: str,
        **kwargs,
    ) -> str:
        """Execute the tool to store X credentials."""

        if self.profile_id is None:
            raise ValueError("Profile ID is required")

        try:
            logger.info("Attempting to store credentials")
            logger.debug(f"Received Contract Principal: {contract_principal}")

            # Create XCreds object
            x_creds = XCredsCreate(
                profile_id=self.profile_id,
                contract_principal=contract_principal,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                access_token=access_token,
                access_secret=access_secret,
                client_id=client_id,
                client_secret=client_secret,
                username=username,
            )

            # Store in database
            stored_creds = backend.create_x_creds(x_creds)

            if stored_creds:
                logger.info(
                    f"Successfully stored X credentials for user {username} with Contract Principal {contract_principal}"
                )
                return f"Successfully stored X credentials for {username} with Contract Principal {contract_principal}"
            logger.error("Failed to store X credentials - no response from backend")
            return "Failed to store X credentials"
        except Exception as e:
            logger.error(f"Error storing X credentials: {str(e)}")
            return f"Error storing X credentials: {str(e)}"

    def _run(
        self,
        contract_principal: str,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_secret: str,
        client_id: str,
        client_secret: str,
        username: str,
        **kwargs,
    ) -> str:
        """Sync version of the tool."""
        return self._deploy(
            contract_principal=contract_principal,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_secret=access_secret,
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            **kwargs,
        )

    async def _arun(
        self,
        contract_principal: str,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_secret: str,
        client_id: str,
        client_secret: str,
        username: str,
        **kwargs,
    ) -> str:
        """Async version of the tool."""
        return self._deploy(
            contract_principal=contract_principal,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_secret=access_secret,
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            **kwargs,
        )
