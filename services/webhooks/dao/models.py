"""Models for DAO webhook service."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExtensionData(BaseModel):
    """Data model for extension creation via webhook."""

    type: str
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None


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


class DAOWebhookResponse(BaseModel):
    """Response model for DAO creation webhook."""

    dao_id: UUID
    extension_ids: Optional[List[UUID]] = None
    token_id: Optional[UUID] = None
