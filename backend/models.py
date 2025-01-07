from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()}
    )


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


class WalletCreate(WalletBase):
    pass


class Wallet(WalletBase):
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
    type: str
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None
    status: Optional[str] = "DRAFT"


class ExtensionCreate(ExtensionBase):
    pass


class Extension(ExtensionBase):
    id: UUID
    created_at: datetime


#
# DAOS
#
class DAOBase(CustomBaseModel):
    name: str
    mission: Optional[str] = None
    description: Optional[str] = None


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


class JobCreate(JobBase):
    pass


class Job(JobBase):
    id: UUID
    created_at: datetime


#
# PROFILES
#
class ProfileBase(CustomBaseModel):
    role: Optional[str] = None
    email: Optional[str] = None
    assigned_agent_address: Optional[str] = None
    username: Optional[str] = None
    discord_username: Optional[str] = None


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
    code: Optional[str] = None
    link: Optional[str] = None
    monetary_ask: Optional[float] = None
    status: Optional[str] = "DRAFT"
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None
    is_deployed: bool = False


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


class TokenCreate(TokenBase):
    pass


class Token(TokenBase):
    id: UUID
    created_at: datetime


#
# X_USERS
#
class XUserBase(CustomBaseModel):
    realname: Optional[str] = None
    username: Optional[str] = None
    user_id: Optional[str] = None


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
    thread_id: Optional[str] = None


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


class AgentFilter(CustomBaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None
    profile_id: Optional[UUID] = None


class ExtensionFilter(CustomBaseModel):
    dao_id: Optional[UUID] = None
    type: Optional[str] = None
    status: Optional[str] = None


class DAOFilter(CustomBaseModel):
    name: Optional[str] = None


class ThreadFilter(CustomBaseModel):
    profile_id: Optional[UUID] = None
    name: Optional[str] = None


class JobFilter(CustomBaseModel):
    thread_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None


class ProfileFilter(CustomBaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    discord_username: Optional[str] = None


class ProposalFilter(CustomBaseModel):
    dao_id: Optional[UUID] = None
    status: Optional[str] = None
    is_deployed: Optional[bool] = None


class StepFilter(CustomBaseModel):
    job_id: Optional[UUID] = None
    role: Optional[str] = None


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


class XUserFilter(CustomBaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    realname: Optional[str] = None


class XTweetFilter(CustomBaseModel):
    author_id: Optional[UUID] = None
    tweet_id: Optional[str] = None
    thread_id: Optional[str] = None
