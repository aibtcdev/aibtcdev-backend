"""Models for DAO webhook service."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ExtensionData(BaseModel):
    """Data model for extension creation via webhook."""

    name: str
    type: str
    subtype: Optional[str] = None
    source: Optional[str] = None
    hash: Optional[str] = None
    sender: Optional[str] = None
    success: Optional[bool] = True
    txId: Optional[str] = None
    address: Optional[str] = None
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None

    @model_validator(mode="after")
    def set_contract_info(self):
        """Set contract_principal and tx_id from address and txId if not provided."""
        if not self.contract_principal and self.address:
            self.contract_principal = self.address
        if not self.tx_id and self.txId:
            self.tx_id = self.txId
        return self


class TokenData(BaseModel):
    """Data model for token creation via webhook."""

    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    symbol: str
    decimals: int = 6
    max_supply: Optional[str] = None
    uri: Optional[str] = None
    image_url: Optional[str] = None
    x_url: Optional[str] = None
    telegram_url: Optional[str] = None
    website_url: Optional[str] = None


class DAOWebhookPayload(BaseModel):
    """Webhook payload for DAO creation."""

    name: str
    mission: Optional[str] = None
    description: Optional[str] = None
    extensions: Optional[List[ExtensionData]] = Field(default_factory=list)
    token: Optional[TokenData] = None

    @model_validator(mode="after")
    def extract_token_from_extensions(self):
        """Extract token information from extensions if token is not provided."""
        if not self.token and self.extensions:
            # Look for a TOKEN extension with subtype DAO
            for ext in self.extensions:
                if ext.type == "TOKEN" and ext.subtype == "DAO":
                    # Create a token from the extension data
                    self.token = TokenData(
                        contract_principal=ext.address,
                        tx_id=ext.txId,
                        name=f"{self.name} Token",
                        symbol="TKN",
                        decimals=6,
                    )
                    break
        return self


class DAOWebhookResponse(BaseModel):
    """Response model for DAO creation webhook."""

    dao_id: UUID
    extension_ids: Optional[List[UUID]] = None
    token_id: Optional[UUID] = None
