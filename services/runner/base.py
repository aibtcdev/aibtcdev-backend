import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from lib.logger import configure_logger
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

logger = configure_logger(__name__)


@dataclass
class RunnerResult:
    """Base class for runner operation results."""

    success: bool
    message: str
    error: Optional[Exception] = None


T = TypeVar("T", bound=RunnerResult)


def get_required_env_var(name: str) -> UUID:
    """Get a required environment variable and convert it to UUID."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} environment variable is not set")
    return UUID(value)


@dataclass
class RunnerConfig:
    """Configuration class for runners."""

    twitter_profile_id: UUID
    twitter_agent_id: UUID
    twitter_wallet_id: UUID

    @classmethod
    def from_env(cls) -> "RunnerConfig":
        """Create configuration from environment variables."""
        from backend.factory import backend
        from backend.models import WalletFilter

        twitter_profile_id = get_required_env_var("AIBTC_TWITTER_PROFILE_ID")
        twitter_agent_id = get_required_env_var("AIBTC_TWITTER_AGENT_ID")

        twitter_wallet = backend.list_wallets(
            filters=WalletFilter(profile_id=twitter_profile_id)
        )
        if not twitter_wallet:
            logger.critical(
                "No Twitter wallet found - critical system component missing"
            )
            raise RuntimeError("Twitter wallet not found")

        return cls(
            twitter_profile_id=twitter_profile_id,
            twitter_agent_id=twitter_agent_id,
            twitter_wallet_id=twitter_wallet[0].id,
        )


class JobType(str, Enum):
    """Enum for different types of jobs."""

    DAO = "dao"
    TWEET = "tweet"
    # Add new job types here


@dataclass
class JobContext:
    """Context information for job execution."""

    job_type: JobType
    config: RunnerConfig
    parameters: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3


class BaseTask(ABC, Generic[T]):
    """Base class for all tasks."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        self.config = config or RunnerConfig.from_env()

    @abstractmethod
    async def execute(self, context: JobContext) -> List[T]:
        """Execute the task with given context."""
        pass

    @abstractmethod
    async def validate(self, context: JobContext) -> bool:
        """Validate the task can be executed with given context."""
        pass
