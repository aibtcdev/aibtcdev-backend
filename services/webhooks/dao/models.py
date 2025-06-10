"""Models for DAO webhook service."""

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContractType(str, Enum):
    """Contract types enum."""

    AGENT = "AGENT"
    BASE = "BASE"
    ACTIONS = "ACTIONS"
    EXTENSIONS = "EXTENSIONS"
    PROPOSALS = "PROPOSALS"
    TOKEN = "TOKEN"


class ClarityVersion(int, Enum):
    """Clarity version enum."""

    CLARITY1 = 1
    CLARITY2 = 2
    CLARITY3 = 3


class ContractCategory(str, Enum):
    """Contract categories enum."""

    BASE = "BASE"
    ACTIONS = "ACTIONS"
    EXTENSIONS = "EXTENSIONS"
    PROPOSALS = "PROPOSALS"
    EXTERNAL = "EXTERNAL"
    TOKEN = "TOKEN"


# Contract subtypes for each type
class AgentSubtype(str, Enum):
    """Agent contract subtypes."""

    AGENT_ACCOUNT = "AGENT_ACCOUNT"


class BaseSubtype(str, Enum):
    """Base contract subtypes."""

    DAO = "DAO"


class ActionsSubtype(str, Enum):
    """Actions contract subtypes."""

    SEND_MESSAGE = "SEND_MESSAGE"


class ExtensionsSubtype(str, Enum):
    """Extensions contract subtypes."""

    ACTION_PROPOSAL_VOTING = "ACTION_PROPOSAL_VOTING"
    DAO_CHARTER = "DAO_CHARTER"
    DAO_EPOCH = "DAO_EPOCH"
    DAO_USERS = "DAO_USERS"
    ONCHAIN_MESSAGING = "ONCHAIN_MESSAGING"
    REWARDS_ACCOUNT = "REWARDS_ACCOUNT"
    TOKEN_OWNER = "TOKEN_OWNER"
    TREASURY = "TREASURY"


class ProposalsSubtype(str, Enum):
    """Proposals contract subtypes."""

    INITIALIZE_DAO = "INITIALIZE_DAO"


class TokenSubtype(str, Enum):
    """Token contract subtypes."""

    DAO = "DAO"
    DEX = "DEX"
    POOL = "POOL"
    PRELAUNCH = "PRELAUNCH"


# Contract subcategories for each category
class BaseSubcategory(str, Enum):
    """Base contract subcategories."""

    DAO = "DAO"


class ActionsSubcategory(str, Enum):
    """Actions contract subcategories."""

    CONFIGURE_TIMED_VAULT_DAO = "CONFIGURE_TIMED_VAULT_DAO"
    CONFIGURE_TIMED_VAULT_SBTC = "CONFIGURE_TIMED_VAULT_SBTC"
    CONFIGURE_TIMED_VAULT_STX = "CONFIGURE_TIMED_VAULT_STX"
    PMT_DAO_ADD_RESOURCE = "PMT_DAO_ADD_RESOURCE"
    PMT_DAO_TOGGLE_RESOURCE = "PMT_DAO_TOGGLE_RESOURCE"
    PMT_SBTC_ADD_RESOURCE = "PMT_SBTC_ADD_RESOURCE"
    PMT_SBTC_TOGGLE_RESOURCE = "PMT_SBTC_TOGGLE_RESOURCE"
    PMT_STX_ADD_RESOURCE = "PMT_STX_ADD_RESOURCE"
    PMT_STX_TOGGLE_RESOURCE = "PMT_STX_TOGGLE_RESOURCE"
    MESSAGING_SEND_MESSAGE = "MESSAGING_SEND_MESSAGE"
    TREASURY_ALLOW_ASSET = "TREASURY_ALLOW_ASSET"


class ExtensionsSubcategory(str, Enum):
    """Extensions contract subcategories."""

    ACTION_PROPOSALS = "ACTION_PROPOSALS"
    CORE_PROPOSALS = "CORE_PROPOSALS"
    CHARTER = "CHARTER"
    MESSAGING = "MESSAGING"
    PAYMENTS_DAO = "PAYMENTS_DAO"
    PAYMENTS_SBTC = "PAYMENTS_SBTC"
    PAYMENTS_STX = "PAYMENTS_STX"
    TIMED_VAULT_DAO = "TIMED_VAULT_DAO"
    TIMED_VAULT_SBTC = "TIMED_VAULT_SBTC"
    TIMED_VAULT_STX = "TIMED_VAULT_STX"
    TOKEN_OWNER = "TOKEN_OWNER"
    TREASURY = "TREASURY"


class ProposalsSubcategory(str, Enum):
    """Proposals contract subcategories."""

    BOOTSTRAP_INIT = "BOOTSTRAP_INIT"


class ExternalSubcategory(str, Enum):
    """External contract subcategories."""

    STANDARD_SIP009 = "STANDARD_SIP009"
    STANDARD_SIP010 = "STANDARD_SIP010"
    FAKTORY_SIP010 = "FAKTORY_SIP010"
    BITFLOW_POOL = "BITFLOW_POOL"
    BITFOW_SIP010 = "BITFOW_SIP010"


class TokenSubcategory(str, Enum):
    """Token contract subcategories."""

    DAO = "DAO"
    DEX = "DEX"
    POOL = "POOL"
    POOL_STX = "POOL_STX"
    PRELAUNCH = "PRELAUNCH"


class DeployedContract(BaseModel):
    """Deployed contract model for the new webhook structure."""

    name: str
    display_name: Optional[str] = Field(None, alias="displayName")
    type: ContractType
    subtype: str  # Handle union of subtypes as string for flexibility
    tx_id: str = Field(alias="txId")
    deployer: str
    contract_principal: str = Field(alias="contractPrincipal")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class TokenInfo(BaseModel):
    """Token information model for DAO webhook."""

    symbol: str
    decimals: int
    max_supply: str = Field(alias="maxSupply")
    uri: str
    image_url: str = Field(alias="imageUrl")
    x_url: Optional[str] = Field(None, alias="xUrl")
    telegram_url: Optional[str] = Field(None, alias="telegramUrl")
    website_url: Optional[str] = Field(None, alias="websiteUrl")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class DAOWebhookPayload(BaseModel):
    """Webhook payload for DAO creation with deployed contracts structure."""

    name: str
    mission: str
    description: Optional[str] = None
    contracts: List[DeployedContract]
    token_info: TokenInfo = Field(alias="tokenInfo")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class DAOWebhookResponse(BaseModel):
    """Response model for DAO creation webhook."""

    dao_id: UUID
    extension_ids: Optional[List[UUID]] = None
    token_id: Optional[UUID] = None


# Legacy models for backward compatibility
class ContractResponse(BaseModel):
    """Contract response model."""

    name: str
    display_name: Optional[str] = Field(None, alias="displayName")
    type: ContractType
    subtype: str  # Handle union of subtypes as string for flexibility
    source: Optional[str] = None
    hash: Optional[str] = None
    deployment_order: Optional[int] = Field(None, alias="deploymentOrder")
    clarity_version: Optional[ClarityVersion] = Field(None, alias="clarityVersion")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class DeployedContractRegistryEntry(ContractResponse):
    """Deployed contract registry entry model."""

    sender: str
    success: bool
    tx_id: Optional[str] = Field(None, alias="txId")
    address: str
    error: Optional[str] = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class TokenData(BaseModel):
    """Token data model for DAO webhook."""

    name: str
    symbol: str
    decimals: int
    description: str
    max_supply: str
    uri: str
    tx_id: str
    contract_principal: str
    image_url: str
    x_url: Optional[str] = None
    telegram_url: Optional[str] = None
    website_url: Optional[str] = None
