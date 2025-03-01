import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from lib.logger import configure_logger

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
    DAO_TWEET = "dao_tweet"
    TWEET = "tweet"
    DAO_PROPOSAL_VOTE = "dao_proposal_vote"
    # Add new job types here

    def __str__(self):
        return self.value


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

    @classmethod
    def get_result_class(cls) -> Type[RunnerResult]:
        """Get the result class for this task."""
        return cls.__orig_bases__[0].__args__[0]  # type: ignore

    async def validate(self, context: JobContext) -> bool:
        """Validate the task can be executed with given context.

        This method provides a structured validation pipeline:
        1. Validate configuration
        2. Validate prerequisites
        3. Validate task-specific conditions
        """
        try:
            logger.info(f"Starting validation for {self.__class__.__name__}")

            # Step 1: Configuration validation
            logger.debug(
                f"{self.__class__.__name__}: Starting configuration validation"
            )
            if not await self._validate_config(context):
                logger.warning(
                    f"{self.__class__.__name__}: Configuration validation failed"
                )
                return False
            logger.debug(f"{self.__class__.__name__}: Configuration validation passed")

            # Step 2: Prerequisites validation
            logger.debug(
                f"{self.__class__.__name__}: Starting prerequisites validation"
            )
            if not await self._validate_prerequisites(context):
                logger.warning(
                    f"{self.__class__.__name__}: Prerequisites validation failed"
                )
                return False
            logger.debug(f"{self.__class__.__name__}: Prerequisites validation passed")

            # Step 3: Task-specific validation
            logger.debug(
                f"{self.__class__.__name__}: Starting task-specific validation"
            )
            if not await self._validate_task_specific(context):
                logger.warning(
                    f"{self.__class__.__name__}: Task-specific validation failed"
                )
                return False
            logger.debug(f"{self.__class__.__name__}: Task-specific validation passed")

            logger.info(f"{self.__class__.__name__}: All validation checks passed")
            return True
        except Exception as e:
            logger.error(
                f"Error in validation for {self.__class__.__name__}: {str(e)}",
                exc_info=True,
            )
            return False

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration.
        Override this method to add custom configuration validation."""
        return True

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites.
        Override this method to add custom prerequisites validation."""
        return True

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions.
        Override this method to add custom task-specific validation."""
        return True

    @abstractmethod
    async def execute(self, context: JobContext) -> List[T]:
        """Execute the task with given context."""
        pass
