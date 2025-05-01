from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()}
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
    CONVERSATION = "thread"
    INVALID = "invalid"

    def __str__(self):
        return self.value


class ProposalType(str, Enum):
    ACTION = "action"
    CORE = "core"

    def __str__(self):
        return self.value


class QueueMessageType(str, Enum):
    TWEET = "tweet"
    DAO = "dao"
    DAO_TWEET = "dao_tweet"
    DAO_PROPOSAL_VOTE = "dao_proposal_vote"
    DAO_PROPOSAL_CONCLUDE = "dao_proposal_conclude"
    DAO_PROPOSAL_EVALUATION = (
        "dao_proposal_evaluation"  # New type for proposal evaluation
    )
    AGENT_ACCOUNT_DEPLOY = (
        "agent_account_deploy"  # New type for agent account deployment
    )

    def __str__(self):
        return self.value


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
#  QUEUE MESSAGES
#
class QueueMessageBase(CustomBaseModel):
    type: Optional[QueueMessageType] = None
    message: Optional[dict] = None
    is_processed: Optional[bool] = False
    tweet_id: Optional[str] = None
    conversation_id: Optional[str] = None
    dao_id: Optional[UUID] = None
    wallet_id: Optional[UUID] = None


class QueueMessageCreate(QueueMessageBase):
    pass


class QueueMessage(QueueMessageBase):
    id: UUID
    created_at: datetime


#
#  WALLETS
#
class WalletBase(CustomBaseModel):
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    mainnet_address: Optional[str] = None
    testnet_address: Optional[str] = None
    secret_id: Optional[UUID] = None


class WalletCreate(WalletBase):
    pass


class Wallet(WalletBase):
    id: UUID
    created_at: datetime


#
#  X_CREDS
#
class XCredsBase(CustomBaseModel):
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    secret_id: Optional[UUID] = None
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None
    access_token: Optional[str] = None
    access_secret: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    username: Optional[str] = None
    dao_id: Optional[UUID] = None


class XCredsCreate(XCredsBase):
    pass


class XCreds(XCredsBase):
    id: UUID
    created_at: datetime


#
#  AGENTS
#
class AgentBase(CustomBaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None
    backstory: Optional[str] = None
    profile_id: Optional[UUID] = None
    agent_tools: Optional[List[str]] = None
    image_url: Optional[str] = None


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
    wallet_id: Optional[UUID] = None
    author_id: Optional[UUID] = None


class DAOCreate(DAOBase):
    pass


class DAO(DAOBase):
    id: UUID
    created_at: datetime


#
# CONVERSATIONS
#
class ThreadBase(CustomBaseModel):
    profile_id: Optional[UUID] = None
    name: Optional[str] = "New Thread"


class ThreadCreate(ThreadBase):
    pass


class Thread(ThreadBase):
    id: UUID
    created_at: datetime


#
# JOBS
#
class JobBase(CustomBaseModel):
    thread_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    input: Optional[str] = None
    result: Optional[str] = None
    tokens: Optional[float] = None
    task_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None


class JobCreate(JobBase):
    pass


class Job(JobBase):
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
    profile_id: Optional[UUID] = None
    is_enabled: Optional[bool] = None


#
# PROFILES
#
class ProfileBase(CustomBaseModel):
    email: Optional[str] = None
    has_dao_agent: Optional[bool] = False
    has_completed_guide: Optional[bool] = False


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
    description: Optional[str] = None
    status: Optional[ContractStatus] = ContractStatus.DRAFT
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None
    proposal_id: Optional[int] = None  # On-chain proposal ID if its an action proposal
    proposal_contract: Optional[str] = (
        None  # Contract address of the proposal if its a core contract proposal
    )
    type: Optional[ProposalType] = ProposalType.ACTION
    action: Optional[str] = None
    caller: Optional[str] = None
    creator: Optional[str] = None
    created_at_block: Optional[int] = None
    end_block: Optional[int] = None
    start_block: Optional[int] = None
    liquid_tokens: Optional[str] = None  # Using string to handle large numbers
    parameters: Optional[str] = None  # Hex encoded parameters
    # Additional fields from blockchain data
    concluded_by: Optional[str] = None
    executed: Optional[bool] = None
    met_quorum: Optional[bool] = None
    met_threshold: Optional[bool] = None
    passed: Optional[bool] = None
    votes_against: Optional[str] = None  # String to handle large numbers
    votes_for: Optional[str] = None  # String to handle large numbers
    bond: Optional[str] = None  # String to handle large numbers


class ProposalCreate(ProposalBase):
    pass


class Proposal(ProposalBase):
    id: UUID
    created_at: datetime


#
# STEPS
#
class StepBase(CustomBaseModel):
    job_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    role: Optional[str] = None
    content: Optional[str] = None
    tool: Optional[str] = None
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    thought: Optional[str] = None
    profile_id: Optional[UUID] = None
    status: Optional[str] = (
        None  # Add status field to track planning, processing, complete
    )


class StepCreate(StepBase):
    pass


class Step(StepBase):
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


class QueueMessageFilter(CustomBaseModel):
    type: Optional[QueueMessageType] = None
    is_processed: Optional[bool] = None
    tweet_id: Optional[str] = None
    conversation_id: Optional[str] = None
    wallet_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None


class AgentFilter(CustomBaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None
    profile_id: Optional[UUID] = None


class ExtensionFilter(CustomBaseModel):
    dao_id: Optional[UUID] = None
    type: Optional[str] = None
    status: Optional[ContractStatus] = None
    contract_principal: Optional[str] = None


class DAOFilter(CustomBaseModel):
    name: Optional[str] = None
    is_deployed: Optional[bool] = None
    is_broadcasted: Optional[bool] = None
    wallet_id: Optional[UUID] = None


class ThreadFilter(CustomBaseModel):
    profile_id: Optional[UUID] = None
    name: Optional[str] = None


class JobFilter(CustomBaseModel):
    thread_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None


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
    proposal_contract: Optional[str] = None


class StepFilter(CustomBaseModel):
    job_id: Optional[UUID] = None
    role: Optional[str] = None
    status: Optional[str] = None  # Add status filter


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
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None


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
    wallet_id: UUID
    token_id: UUID
    dao_id: UUID  # Direct reference to the DAO for easier queries
    amount: str  # String to handle large numbers precisely
    updated_at: datetime = datetime.now()


class HolderCreate(HolderBase):
    pass


class Holder(HolderBase):
    id: UUID
    created_at: datetime


class HolderFilter(CustomBaseModel):
    wallet_id: Optional[UUID] = None
    token_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None


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
    prompt: Optional[str] = None
    voted: Optional[bool] = None
    cost: Optional[float] = None
    model: Optional[str] = None
    profile_id: Optional[UUID] = None


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


# Add this to your backend interface class to get agents by tokens
class AgentWithWalletTokenDTO(CustomBaseModel):
    agent_id: UUID
    agent_name: str
    wallet_id: UUID
    wallet_address: str
    token_id: UUID
    token_amount: str
    dao_id: UUID
    dao_name: str


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
    model: Optional[str] = "gpt-4.1"
    temperature: Optional[float] = 0.1  # Add temperature field with default value


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
