from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class Profile(BaseModel):
    account_index: int
    id: str


class Creator(BaseModel):
    email: str


class Task(BaseModel):
    id: int
    description: str
    expected_output: str
    agent_id: int
    profile_id: str


class Agent(BaseModel):
    id: int
    name: str
    role: str
    goal: str
    backstory: str
    agent_tools: List[str]
    tasks: List[Task]


class Crew(BaseModel):
    id: int
    name: str
    description: str
    created_at: str
    creator_email: str
    agents: List[Agent]


# Base Response Models
class BaseResponse(BaseModel):
    """Base response model with success and optional error fields."""

    success: bool
    error: Optional[str] = None


# User Profile Models
class UserProfile(BaseModel):
    """User profile model."""

    id: int
    stx_address: str
    user_role: str
    account_index: Optional[int] = None
    bns_address: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProfileResponse(BaseResponse):
    """Response model for profile operations."""

    profile: Optional[UserProfile] = None
    profiles: Optional[List[UserProfile]] = None


class RoleResponse(BaseResponse):
    """Response model for role operations."""

    role: Optional[str] = None


# Task Models
class UserTask(BaseModel):
    """User task model."""

    id: int
    task_name: str
    task_description: str
    task_expected_output: str
    agent_id: int
    created_at: datetime
    updated_at: datetime


class TaskResponse(BaseResponse):
    """Response model for task operations."""

    task: Optional[UserTask] = None
    tasks: Optional[List[UserTask]] = None


# Crew Models
class UserCrew(BaseModel):
    """User crew model."""

    id: int
    crew_name: str
    crew_description: str
    crew_is_public: bool
    crew_is_cron: bool = False
    profile_id: str
    created_at: datetime
    updated_at: datetime


class CrewExecution(BaseModel):
    """Crew execution model."""

    id: int
    profile_id: str
    crew_id: int
    conversation_id: int
    user_input: Optional[str]
    total_tokens: int
    successful_requests: int
    created_at: datetime
    updated_at: datetime


class UserCrewExecutionStep(BaseModel):
    """Crew execution step model."""

    id: int
    profile_id: str
    crew_id: int
    execution_id: int
    step_type: str
    step_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CrewResponse(BaseResponse):
    """Response model for crew operations."""

    crew: Optional[UserCrew] = None
    crews: Optional[List[UserCrew]] = None
    execution: Optional[CrewExecution] = None
    executions: Optional[List[CrewExecution]] = None


class CrewStepResponse(BaseResponse):
    """Response model for crew execution step operations."""

    step: Optional[UserCrewExecutionStep] = None
    steps: Optional[List[UserCrewExecutionStep]] = None


# Agent Models
class UserAgent(BaseModel):
    """User agent model."""

    id: int
    profile_id: str
    crew_id: int
    agent_name: str
    agent_role: str
    agent_goal: str
    agent_backstory: str
    created_at: datetime
    updated_at: datetime


class AgentResponse(BaseResponse):
    """Response model for agent operations."""

    agent: Optional[UserAgent] = None
    agents: Optional[List[UserAgent]] = None


# Twitter Models
class XBotAuthor(BaseModel):
    """Twitter author model."""

    id: int
    author_id: str
    realname: Optional[str]
    username: Optional[str]
    created_at: datetime
    updated_at: datetime


class XBotTweet(BaseModel):
    """Twitter tweet model."""

    id: int
    tweet_id: str
    tweet_body: str
    author_id: str
    thread_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class XBotLog(BaseModel):
    """Twitter log model."""

    id: int
    tweet_id: str
    status: str
    message: Optional[str]
    created_at: datetime
    updated_at: datetime


class TwitterResponse(BaseResponse):
    """Response model for Twitter operations."""

    author: Optional[XBotAuthor] = None
    authors: Optional[List[XBotAuthor]] = None
    tweet: Optional[XBotTweet] = None
    tweets: Optional[List[XBotTweet]] = None
    log: Optional[XBotLog] = None
    logs: Optional[List[XBotLog]] = None


# Image Models
class ImageGenerationResponse(BaseResponse):
    """Response model for image generation."""

    image_key: str
    url: str
    created_at: datetime


class ImageListResponse(BaseResponse):
    """Response model for image listing."""

    images: List[Dict[str, Any]]
    cursor: Optional[str]


# Cron Models
class UserCron(BaseModel):
    """User cron model."""

    id: int
    profile_id: str
    crew_id: int
    AIBTC_CRON_ENABLED: bool
    cron_interval: str = "0 * * * *"  # Default to hourly
    cron_input: str = ""
    created_at: datetime
    updated_at: datetime


class CronResponse(BaseResponse):
    """Response model for cron operations."""

    cron: Optional[UserCron] = None
    crons: Optional[List[UserCron]] = None


# Auth Models
class AuthResponse(BaseResponse):
    """Response model for authentication."""

    token: str
    expires_at: datetime


class VerificationResponse(BaseResponse):
    """Response model for verification."""

    valid: bool
    address: Optional[str]
