from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
        arbitrary_types_allowed=True,
    )


# need to create status enum
class ContractStatus(Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    DEPLOYED = "DEPLOYED"
    FAILED = "FAILED"

    def __str__(self):
        return self.value


class ChainStateBase(CustomBaseModel):
    """Base model for tracking blockchain state."""

    block_height: Optional[int] = None
    block_hash: Optional[str] = None
    network: Optional[str] = "mainnet"  # mainnet or testnet
    bitcoin_block_height: Optional[int] = None
    chainhook_uuid: Optional[str] = None


class ChainStateCreate(ChainStateBase):
    pass


class ChainState(ChainStateBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ChainStateFilter(CustomBaseModel):
    network: Optional[str] = None


class TweetType(str, Enum):
    TOOL_REQUEST = "tool_request"
    INVALID = "invalid"

    def __str__(self):
        return self.value


class ProposalType(str, Enum):
    ACTION = "action"
    CORE = "core"

    def __str__(self):
        return self.value


class QueueMessageType:
    """Dynamic queue message types that are registered at runtime.

    This system is compatible with the runner's dynamic JobType system.
    Queue message types are registered dynamically as job tasks are discovered.
    """

    _message_types: Dict[str, "QueueMessageType"] = {}

    def __init__(self, value: str):
        self._value = value.lower()
        self._name = value.upper()

    @property
    def value(self) -> str:
        return self._value

    @property
    def name(self) -> str:
        return self._name

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"QueueMessageType({self._value})"

    def __eq__(self, other) -> bool:
        if isinstance(other, QueueMessageType):
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other.lower()
        return False

    def __hash__(self) -> int:
        return hash(self._value)

    def __json__(self) -> str:
        """Custom JSON serialization for Pydantic."""
        return self._value

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """Custom Pydantic schema for serialization/deserialization."""
        from pydantic_core import core_schema

        def validate_queue_message_type(value):
            if value is None:
                return None
            if isinstance(value, cls):
                return value
            if isinstance(value, str):
                return cls.get_or_create(value)
            raise ValueError(f"Invalid QueueMessageType value: {value}")

        return core_schema.no_info_plain_validator_function(
            validate_queue_message_type,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def get_or_create(cls, message_type: str) -> "QueueMessageType":
        """Get existing message type or create new one."""
        normalized = message_type.lower()
        if normalized not in cls._message_types:
            cls._message_types[normalized] = cls(normalized)
        return cls._message_types[normalized]

    @classmethod
    def register(cls, message_type: str) -> "QueueMessageType":
        """Register a new message type and return the instance."""
        return cls.get_or_create(message_type)

    @classmethod
    def get_all_message_types(cls) -> Dict[str, str]:
        """Get all registered message types."""
        return {mt._value: mt._value for mt in cls._message_types.values()}

    @classmethod
    def list_all(cls) -> List["QueueMessageType"]:
        """Get all registered message type instances."""
        return list(cls._message_types.values())


# Types are registered dynamically by the runner system
# No need to pre-register common types


#
#  QUEUE MESSAGES
#
class QueueMessageBase(CustomBaseModel):
    """Base model for queue messages.

    The message field supports multiple formats:

    1. New chunked format (recommended for tweets):
    {
        "chunks": ["First chunk text (1/3)", "Second chunk text (2/3)", "Third chunk text (3/3)"],
        "total_chunks": 3
    }

    2. Legacy format (backward compatibility):
    {
        "message": "Main message content",
        "follow_up_message": "Optional follow-up content",
        "reply_to_tweet_id": "optional_tweet_id_for_threading"
    }

    3. Discord format:
    {
        "content": "Discord message content",
        "proposal_status": "passed" or "failed"
    }
    """

    type: Optional[QueueMessageType] = None
    message: Optional[dict] = None
    is_processed: Optional[bool] = False
    dao_id: Optional[UUID] = None
    wallet_id: Optional[UUID] = None
    result: Optional[dict] = None


class QueueMessageCreate(QueueMessageBase):
    pass


class QueueMessage(QueueMessageBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


#
#  SECRETS
#
class SecretBase(CustomBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    secret: Optional[str] = None
    decrypted_secret: Optional[str] = None
    key_id: Optional[str] = None
    nonce: Optional[str] = None


class SecretCreate(SecretBase):
    pass


class Secret(SecretBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


#
#  WALLETS
#
class WalletBase(CustomBaseModel):
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    mainnet_address: Optional[str] = None
    testnet_address: Optional[str] = None
    secret_id: Optional[UUID] = None
    stx_balance: Optional[str] = None  # String to handle large numbers precisely
    balance_updated_at: Optional[datetime] = None  # When balance was last checked


class WalletCreate(WalletBase):
    pass


class Wallet(WalletBase):
    id: UUID
    created_at: datetime


#
#  X_CREDS
#
class XCredsBase(CustomBaseModel):
    secret_id: Optional[UUID] = None
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None
    access_token: Optional[str] = None
    access_secret: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    username: Optional[str] = None
    dao_id: Optional[UUID] = None
    bearer_token: Optional[str] = None


class XCredsCreate(XCredsBase):
    pass


class XCreds(XCredsBase):
    id: UUID
    created_at: datetime


#
#  AGENTS
#
class AgentBase(CustomBaseModel):
    profile_id: Optional[UUID] = None
    account_contract: Optional[str] = None
    approved_contracts: Optional[List[str]] = (
        None  # Array of approved contract principals
    )


class AgentCreate(AgentBase):
    pass


class Agent(AgentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


#
# CAPABILITIES
#
class ExtensionBase(CustomBaseModel):
    dao_id: Optional[UUID] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None
    status: Optional[ContractStatus] = ContractStatus.DRAFT


class ExtensionCreate(ExtensionBase):
    pass


class Extension(ExtensionBase):
    id: UUID
    created_at: datetime


#
# DAOS
#
class DAOBase(CustomBaseModel):
    name: Optional[str] = None
    mission: Optional[str] = None
    description: Optional[str] = None
    is_deployed: Optional[bool] = False
    is_broadcasted: Optional[bool] = False


class DAOCreate(DAOBase):
    pass


class DAO(DAOBase):
    id: UUID
    created_at: datetime


#
# KEYS
#
class KeyBase(CustomBaseModel):
    profile_id: Optional[UUID] = None
    is_enabled: Optional[bool] = True


class KeyCreate(KeyBase):
    pass


class Key(KeyBase):
    id: UUID
    created_at: datetime


class KeyFilter(CustomBaseModel):
    id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    is_enabled: Optional[bool] = None


#
# PROFILES
#
class ProfileBase(CustomBaseModel):
    email: Optional[str] = None
    has_dao_agent: Optional[bool] = False
    has_completed_guide: Optional[bool] = False
    mainnet_address: Optional[str] = None
    testnet_address: Optional[str] = None


class ProfileCreate(ProfileBase):
    pass


class Profile(ProfileBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None


#
# PROPOSALS
#
class ProposalBase(CustomBaseModel):
    dao_id: Optional[UUID] = None
    title: Optional[str] = None
    content: Optional[str] = None  # Replaces both description and parameters
    status: Optional[ContractStatus] = ContractStatus.DRAFT
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None
    proposal_id: Optional[int] = None  # On-chain proposal ID if its an action proposal
    type: Optional[ProposalType] = ProposalType.ACTION
    action: Optional[str] = None
    caller: Optional[str] = None
    creator: Optional[str] = None
    liquid_tokens: Optional[str] = None  # Using string to handle large numbers
    # Additional fields from blockchain data
    concluded_by: Optional[str] = None
    executed: Optional[bool] = None
    met_quorum: Optional[bool] = None
    met_threshold: Optional[bool] = None
    passed: Optional[bool] = None
    votes_against: Optional[str] = None  # String to handle large numbers
    votes_for: Optional[str] = None  # String to handle large numbers
    bond: Optional[str] = None  # String to handle large numbers
    # Fields from updated chainhook payload
    contract_caller: Optional[str] = None
    created_btc: Optional[int] = None
    created_stx: Optional[int] = None
    creator_user_id: Optional[int] = None
    exec_end: Optional[int] = None
    exec_start: Optional[int] = None
    memo: Optional[str] = None
    tx_sender: Optional[str] = None
    vote_end: Optional[int] = None
    vote_start: Optional[int] = None
    voting_delay: Optional[int] = None
    voting_period: Optional[int] = None
    voting_quorum: Optional[int] = None
    voting_reward: Optional[str] = None  # String to handle large numbers
    voting_threshold: Optional[int] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    has_embedding: Optional[bool] = (
        False  # Flag to track if proposal has been embedded in vector store
    )
    x_url: Optional[str] = None  # Twitter/X URL associated with the proposal
    tweet_id: Optional[UUID] = None  # Reference to x_tweets table for linked tweet data
    airdrop_id: Optional[UUID] = (
        None  # Reference to airdrops table for linked airdrop data
    )


class ProposalCreate(ProposalBase):
    pass


class Proposal(ProposalBase):
    id: UUID
    created_at: datetime


#
# TASKS
#
class TaskBase(CustomBaseModel):
    prompt: Optional[str] = None
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    name: Optional[str] = None
    cron: Optional[str] = None
    is_scheduled: Optional[bool] = False


class TaskCreate(TaskBase):
    pass


class Task(TaskBase):
    id: UUID
    created_at: datetime


#
# TELEGRAM USERS
#
class TelegramUserBase(CustomBaseModel):
    telegram_user_id: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    registered: bool = False
    profile_id: Optional[UUID] = None
    is_registered: bool = False


class TelegramUserCreate(TelegramUserBase):
    pass


class TelegramUser(TelegramUserBase):
    id: UUID
    created_at: datetime


#
# TOKENS
#
class TokenBase(CustomBaseModel):
    dao_id: Optional[UUID] = None
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    symbol: Optional[str] = None
    decimals: Optional[int] = None
    max_supply: Optional[str] = None
    uri: Optional[str] = None
    image_url: Optional[str] = None
    x_url: Optional[str] = None
    telegram_url: Optional[str] = None
    website_url: Optional[str] = None
    status: Optional[ContractStatus] = ContractStatus.DRAFT


class TokenCreate(TokenBase):
    pass


class Token(TokenBase):
    id: UUID
    created_at: datetime


#
# X_USERS
#
class XUserBase(CustomBaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    user_id: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    profile_image_url: Optional[str] = None
    profile_banner_url: Optional[str] = None
    protected: Optional[bool] = None
    url: Optional[str] = None
    verified: Optional[bool] = None
    verified_type: Optional[str] = None
    subscription_type: Optional[str] = None
    bitcoin_face_score: Optional[float] = (
        None  # Score from HuggingFace bitcoin face analysis
    )


class XUserCreate(XUserBase):
    pass


class XUser(XUserBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None


#
# X_TWEETS
#
class XTweetBase(CustomBaseModel):
    message: Optional[str] = None
    author_id: Optional[UUID] = None
    tweet_id: Optional[str] = None
    conversation_id: Optional[str] = None
    is_worthy: Optional[bool] = False
    tweet_type: Optional[TweetType] = TweetType.INVALID
    confidence_score: Optional[float] = None
    reason: Optional[str] = None
    images: Optional[List[str]] = None  # Array of image URLs attached to the tweet
    # Store additional tweet metadata
    author_name: Optional[str] = None
    author_username: Optional[str] = None
    created_at_twitter: Optional[str] = None  # Original tweet creation date
    public_metrics: Optional[Dict[str, Any]] = None  # Retweet count, like count, etc.
    entities: Optional[Dict[str, Any]] = None  # URLs, hashtags, mentions
    attachments: Optional[Dict[str, Any]] = None  # Media attachments info
    tweet_images_analysis: Optional[List[Dict[str, Any]]] = (
        None  # Bitcoin face analysis for tweet images
    )


class XTweetCreate(XTweetBase):
    pass


class XTweet(XTweetBase):
    id: UUID
    created_at: datetime


# -----------------------------------------------------
# 2) Filter Models (Typed)
# -----------------------------------------------------
#
# Each table gets its own Filter class with optional fields
# you might want to filter on in the "list" methods.
#


class WalletFilter(CustomBaseModel):
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    mainnet_address: Optional[str] = None
    testnet_address: Optional[str] = None
    stx_balance: Optional[str] = None  # Filter by exact balance
    balance_updated_at: Optional[datetime] = None  # Filter by balance update time


class WalletFilterN(CustomBaseModel):
    """Enhanced wallet filter with support for batch operations using 'in_' queries."""

    # Standard equality filters (same as WalletFilter)
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    mainnet_address: Optional[str] = None
    testnet_address: Optional[str] = None
    stx_balance: Optional[str] = None  # Filter by exact balance
    balance_updated_at: Optional[datetime] = None  # Filter by balance update time

    # Batch filters using 'in_' operations
    ids: Optional[List[UUID]] = None
    agent_ids: Optional[List[UUID]] = None
    profile_ids: Optional[List[UUID]] = None
    mainnet_addresses: Optional[List[str]] = None
    testnet_addresses: Optional[List[str]] = None

    # Balance range filters
    stx_balance_gte: Optional[str] = None  # Balance greater than or equal
    stx_balance_lte: Optional[str] = None  # Balance less than or equal
    balance_updated_before: Optional[datetime] = None  # Balance updated before datetime
    balance_updated_after: Optional[datetime] = None  # Balance updated after datetime


class QueueMessageFilter(CustomBaseModel):
    type: Optional[QueueMessageType] = None
    is_processed: Optional[bool] = None
    wallet_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None


class AgentFilter(CustomBaseModel):
    profile_id: Optional[UUID] = None
    account_contract: Optional[str] = None


class ExtensionFilter(CustomBaseModel):
    dao_id: Optional[UUID] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    status: Optional[ContractStatus] = None
    contract_principal: Optional[str] = None


class DAOFilter(CustomBaseModel):
    name: Optional[str] = None
    is_deployed: Optional[bool] = None
    is_broadcasted: Optional[bool] = None


class ProfileFilter(CustomBaseModel):
    email: Optional[str] = None
    has_dao_agent: Optional[bool] = None
    has_completed_guide: Optional[bool] = None


class ProposalFilter(CustomBaseModel):
    dao_id: Optional[UUID] = None
    status: Optional[ContractStatus] = None
    contract_principal: Optional[str] = None
    proposal_id: Optional[int] = None
    executed: Optional[bool] = None
    passed: Optional[bool] = None
    met_quorum: Optional[bool] = None
    met_threshold: Optional[bool] = None
    type: Optional[ProposalType] = None
    tx_id: Optional[str] = None
    has_embedding: Optional[bool] = None  # Filter by embedding presence


class ProposalFilterN(CustomBaseModel):
    """Enhanced proposal filter with support for batch operations using 'in_' queries."""

    # Standard equality filters (same as ProposalFilter)
    dao_id: Optional[UUID] = None
    status: Optional[ContractStatus] = None
    contract_principal: Optional[str] = None
    proposal_id: Optional[int] = None
    executed: Optional[bool] = None
    passed: Optional[bool] = None
    met_quorum: Optional[bool] = None
    met_threshold: Optional[bool] = None
    type: Optional[ProposalType] = None

    # Batch filters using 'in_' operations
    dao_ids: Optional[List[UUID]] = None
    proposal_ids: Optional[List[int]] = None
    statuses: Optional[List[ContractStatus]] = None
    contract_principals: Optional[List[str]] = None
    types: Optional[List[ProposalType]] = None

    # Range filters for numeric fields
    proposal_id_gte: Optional[int] = None  # greater than or equal
    proposal_id_lte: Optional[int] = None  # less than or equal

    # Text search (if supported by backend)
    title_contains: Optional[str] = None
    content_contains: Optional[str] = None


class TaskFilter(CustomBaseModel):
    profile_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    is_scheduled: Optional[bool] = None


class SecretFilter(CustomBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TelegramUserFilter(CustomBaseModel):
    telegram_user_id: Optional[str] = None
    profile_id: Optional[UUID] = None
    is_registered: Optional[bool] = None


class TokenFilter(CustomBaseModel):
    dao_id: Optional[UUID] = None
    name: Optional[str] = None
    symbol: Optional[str] = None
    contract_principal: Optional[str] = None
    status: Optional[ContractStatus] = None


class XCredsFilter(CustomBaseModel):
    dao_id: Optional[UUID] = None
    username: Optional[str] = None


class XUserFilter(CustomBaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    profile_image_url: Optional[str] = None
    profile_banner_url: Optional[str] = None
    protected: Optional[bool] = None
    url: Optional[str] = None
    verified: Optional[bool] = None
    verified_type: Optional[str] = None
    subscription_type: Optional[str] = None
    bitcoin_face_score: Optional[float] = None


class XTweetFilter(CustomBaseModel):
    author_id: Optional[UUID] = None
    tweet_id: Optional[str] = None
    conversation_id: Optional[str] = None
    is_worthy: Optional[bool] = None
    tweet_type: Optional[TweetType] = None
    confidence_score: Optional[float] = None
    reason: Optional[str] = None


#
# HOLDERS
#
class HolderBase(CustomBaseModel):
    wallet_id: Optional[UUID] = None
    token_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None  # Direct reference to the DAO for easier queries
    address: Optional[str] = None
    amount: str  # String to handle large numbers precisely
    updated_at: datetime = datetime.now()


class HolderCreate(HolderBase):
    pass


class Holder(HolderBase):
    id: UUID
    created_at: datetime


class HolderFilter(CustomBaseModel):
    agent_id: Optional[UUID] = None
    wallet_id: Optional[UUID] = None
    token_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    address: Optional[str] = None


#
# VOTES
#
class VoteBase(CustomBaseModel):
    wallet_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    answer: Optional[bool] = None
    proposal_id: Optional[UUID] = None
    reasoning: Optional[str] = None
    tx_id: Optional[str] = None
    address: Optional[str] = None
    amount: Optional[str] = None  # String to handle large token amounts
    confidence: Optional[float] = None
    voted: Optional[bool] = None
    cost: Optional[float] = None
    model: Optional[str] = None
    profile_id: Optional[UUID] = None
    evaluation_score: Optional[Dict[str, Any]] = (
        None  # Store final score from proposal evaluation
    )
    flags: Optional[List[str]] = None  # Store flags from proposal evaluation
    evaluation: Optional[Dict[str, Any]] = (
        None  # Store evaluation from proposal evaluation
    )


class VoteCreate(VoteBase):
    pass


class Vote(VoteBase):
    id: UUID
    created_at: datetime


class VoteFilter(CustomBaseModel):
    wallet_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    proposal_id: Optional[UUID] = None
    answer: Optional[bool] = None
    address: Optional[str] = None
    voted: Optional[bool] = None
    model: Optional[str] = None
    tx_id: Optional[str] = None
    profile_id: Optional[UUID] = None
    evaluation_score: Optional[Dict[str, Any]] = None  # Filter by evaluation score
    flags: Optional[List[str]] = None  # Filter by flags

    # Batch filters for efficient querying
    wallet_ids: Optional[List[UUID]] = None
    proposal_ids: Optional[List[UUID]] = None
    proposal_wallet_pairs: Optional[List[tuple[UUID, UUID]]] = (
        None  # (proposal_id, wallet_id) pairs
    )


#
# VETOS
#
class VetoBase(CustomBaseModel):
    """Base model for proposal vetos."""

    wallet_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    proposal_id: Optional[UUID] = None
    tx_id: Optional[str] = None
    address: Optional[str] = None  # Vetoer address
    amount: Optional[str] = None  # String to handle large token amounts
    contract_caller: Optional[str] = None  # Contract that called the veto
    tx_sender: Optional[str] = None  # Transaction sender
    vetoer_user_id: Optional[int] = None  # User ID of the vetoer
    reasoning: Optional[str] = None  # Optional reasoning for the veto
    profile_id: Optional[UUID] = None


class VetoCreate(VetoBase):
    pass


class Veto(VetoBase):
    id: UUID
    created_at: datetime


class VetoFilter(CustomBaseModel):
    """Filter model for vetos."""

    wallet_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    proposal_id: Optional[UUID] = None
    address: Optional[str] = None
    tx_id: Optional[str] = None
    contract_caller: Optional[str] = None
    tx_sender: Optional[str] = None
    vetoer_user_id: Optional[int] = None
    profile_id: Optional[UUID] = None


# Add this to your backend interface class to get agents by tokens
class AgentWithWalletTokenDTO(CustomBaseModel):
    agent_id: UUID
    wallet_id: UUID
    wallet_address: str
    token_id: UUID
    token_amount: str
    dao_id: UUID
    dao_name: str


#
# FEEDBACK
#
class FeedbackBase(CustomBaseModel):
    """Base model for proposal feedback."""

    profile_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    proposal_id: Optional[UUID] = None
    is_like: Optional[bool] = None  # True for like, False for dislike
    reasoning: Optional[str] = None  # Optional text explaining the feedback


class FeedbackCreate(FeedbackBase):
    pass


class Feedback(FeedbackBase):
    id: UUID
    created_at: datetime


class FeedbackFilter(CustomBaseModel):
    """Filter model for feedback."""

    profile_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    proposal_id: Optional[UUID] = None
    is_like: Optional[bool] = None

    # Batch filters for efficient querying
    profile_ids: Optional[List[UUID]] = None
    proposal_ids: Optional[List[UUID]] = None


#
# AGENT PROMPTS
#
class PromptBase(CustomBaseModel):
    """Base model for prompts."""

    dao_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    prompt_text: Optional[str] = None
    is_active: Optional[bool] = True
    model: Optional[str] = "x-ai/grok-4"
    temperature: Optional[float] = 0.9  # Add temperature field with default value


class PromptCreate(PromptBase):
    pass


class Prompt(PromptBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None


class PromptFilter(CustomBaseModel):
    dao_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    is_active: Optional[bool] = None


#
# LOTTERY RESULTS
#
class LotteryResultBase(CustomBaseModel):
    """Base model for lottery results with quorum-aware selection."""

    proposal_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    bitcoin_block_height: Optional[int] = None
    bitcoin_block_hash: Optional[str] = None
    lottery_seed: Optional[str] = None

    # Enhanced wallet tracking with token amounts
    selected_wallets: Optional[List[Dict[str, Any]]] = (
        None  # [{"wallet_id": str, "token_amount": str}]
    )

    # Quorum tracking fields
    liquid_tokens_at_creation: Optional[str] = None  # Total liquid supply from proposal
    quorum_threshold: Optional[str] = (
        None  # 15% of liquid_tokens (or custom percentage)
    )
    total_selected_tokens: Optional[str] = None  # Sum of selected wallet token amounts
    quorum_achieved: Optional[bool] = None  # Whether we met the quorum threshold
    quorum_percentage: Optional[float] = 0.15  # Default 15% quorum

    # Metadata about the selection
    total_eligible_wallets: Optional[int] = None
    total_eligible_tokens: Optional[str] = None  # Sum of all available tokens
    selection_rounds: Optional[int] = None  # How many lottery rounds were needed
    max_selections: Optional[int] = 100  # Safety cap to prevent runaway selection

    # Legacy field for backward compatibility
    selected_wallet_ids: Optional[List[UUID]] = None


class LotteryResultCreate(LotteryResultBase):
    pass


class LotteryResult(LotteryResultBase):
    id: UUID
    created_at: datetime


class LotteryResultFilter(CustomBaseModel):
    """Filter model for lottery results."""

    proposal_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    bitcoin_block_height: Optional[int] = None
    bitcoin_block_hash: Optional[str] = None


#
# AIRDROPS
#
class AirdropBase(CustomBaseModel):
    """Base model for airdrops."""

    tx_hash: Optional[str] = None
    block_height: Optional[int] = None
    timestamp: Optional[datetime] = None
    sender: Optional[str] = None
    contract_identifier: Optional[str] = None
    token_identifier: Optional[str] = None
    success: Optional[bool] = None
    total_amount_airdropped: Optional[str] = (
        None  # Using string to handle large numbers
    )
    recipients: Optional[List[str]] = None
    proposal_id: Optional[UUID] = None


class AirdropCreate(AirdropBase):
    pass


class Airdrop(AirdropBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None


class AirdropFilter(CustomBaseModel):
    tx_hash: Optional[str] = None
    block_height: Optional[int] = None
    sender: Optional[str] = None
    contract_identifier: Optional[str] = None
    token_identifier: Optional[str] = None
    success: Optional[bool] = None
    proposal_id: Optional[UUID] = None
    # Range filters
    block_height_gte: Optional[int] = None
    block_height_lte: Optional[int] = None
    timestamp_after: Optional[datetime] = None
    timestamp_before: Optional[datetime] = None
