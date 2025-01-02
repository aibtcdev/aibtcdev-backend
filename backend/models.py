from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()}
    )


#
#  WALLETS
#
class WalletBase(CustomBaseModel):
    account_index: Optional[int] = None
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None


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
    agent_tools: Optional[str] = None
    crew_id: Optional[UUID] = None
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
class CapabilityBase(CustomBaseModel):
    collective_id: Optional[UUID] = None
    type: str
    contract_principal: Optional[str] = None
    tx_id: Optional[str] = None
    status: Optional[str] = "DRAFT"


class CapabilityCreate(CapabilityBase):
    pass


class Capability(CapabilityBase):
    id: UUID
    created_at: datetime


#
# COLLECTIVES
#
class CollectiveBase(CustomBaseModel):
    name: str
    mission: Optional[str] = None
    description: Optional[str] = None


class CollectiveCreate(CollectiveBase):
    pass


class Collective(CollectiveBase):
    id: UUID
    created_at: datetime


#
# CONVERSATIONS
#
class ConversationBase(CustomBaseModel):
    profile_id: Optional[UUID] = None
    name: Optional[str] = "New Conversation"


class ConversationCreate(ConversationBase):
    pass


class Conversation(ConversationBase):
    id: UUID
    created_at: datetime


#
# CREWS
#
class CrewBase(CustomBaseModel):
    name: Optional[str] = None
    profile_id: Optional[UUID] = None
    description: Optional[str] = None
    executions: Optional[float] = None
    is_public: bool = False


class CrewCreate(CrewBase):
    pass


class Crew(CrewBase):
    id: UUID
    created_at: datetime


#
# CRONS
#
class CronBase(CustomBaseModel):
    profile_id: Optional[UUID] = None
    crew_id: Optional[UUID] = None
    is_enabled: Optional[bool] = False
    interval: Optional[str] = None
    input: Optional[str] = None


class CronCreate(CronBase):
    pass


class Cron(CronBase):
    id: UUID
    created_at: datetime


#
# JOBS
#
class JobBase(CustomBaseModel):
    conversation_id: Optional[UUID] = None
    crew_id: Optional[UUID] = None
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
    account_index: int


#
# PROPOSALS
#
class ProposalBase(CustomBaseModel):
    collective_id: Optional[UUID] = None
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
    crew_id: Optional[UUID] = None
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
    collective_id: Optional[UUID] = None
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


class XUserCreate(XUserBase):
    pass


class XUser(XUserBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None


#
# X_TWEETS
#
class XTweetBase(CustomBaseModel):
    message: Optional[str] = None
    author_id: Optional[str] = None


class XTweetCreate(XTweetBase):
    pass


class XTweet(XTweetBase):
    id: str
    created_at: datetime


# -----------------------------------------------------
# 2) Filter Models (Typed)
# -----------------------------------------------------
#
# Each table gets its own Filter class with optional fields
# you might want to filter on in the "list" methods.
#
# Example: AgentFilter can filter by name, role, or crew_id
# etc. Extend to any fields you need to filter by.
#


class WalletFilter(CustomBaseModel):
    agent_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None


class AgentFilter(CustomBaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None
    profile_id: Optional[UUID] = None
    crew_id: Optional[UUID] = None


class CapabilityFilter(CustomBaseModel):
    collective_id: Optional[UUID] = None
    type: Optional[str] = None
    status: Optional[str] = None


class CollectiveFilter(CustomBaseModel):
    name: Optional[str] = None


class ConversationFilter(CustomBaseModel):
    profile_id: Optional[UUID] = None
    name: Optional[str] = None


class CrewFilter(CustomBaseModel):
    name: Optional[str] = None
    profile_id: Optional[UUID] = None
    is_public: Optional[bool] = None


class CronFilter(CustomBaseModel):
    profile_id: Optional[UUID] = None
    crew_id: Optional[UUID] = None
    is_enabled: Optional[bool] = None


class JobFilter(CustomBaseModel):
    conversation_id: Optional[UUID] = None
    crew_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None


class ProfileFilter(CustomBaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    discord_username: Optional[str] = None


class ProposalFilter(CustomBaseModel):
    collective_id: Optional[UUID] = None
    status: Optional[str] = None
    is_deployed: Optional[bool] = None


class StepFilter(CustomBaseModel):
    job_id: Optional[UUID] = None
    role: Optional[str] = None


class TaskFilter(CustomBaseModel):
    profile_id: Optional[UUID] = None
    crew_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    is_scheduled: Optional[bool] = None


class TelegramUserFilter(CustomBaseModel):
    telegram_user_id: Optional[str] = None
    profile_id: Optional[UUID] = None
    is_registered: Optional[bool] = None


class TokenFilter(CustomBaseModel):
    collective_id: Optional[UUID] = None
    name: Optional[str] = None
    symbol: Optional[str] = None


class XUserFilter(CustomBaseModel):
    username: Optional[str] = None
    realname: Optional[str] = None


class XTweetFilter(CustomBaseModel):
    author_id: Optional[str] = None
