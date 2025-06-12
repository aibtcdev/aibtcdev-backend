import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
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
    twitter_wallet_id: Optional[UUID]

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

        twitter_wallet_id = None
        if not twitter_wallet:
            logger.warning(
                "No Twitter wallet found - some functionality may be limited"
            )
        else:
            twitter_wallet_id = twitter_wallet[0].id

        return cls(
            twitter_profile_id=twitter_profile_id,
            twitter_agent_id=twitter_agent_id,
            twitter_wallet_id=twitter_wallet_id,
        )


class JobType(str, Enum):
    """Types of jobs that can be run."""

    DAO = "dao"
    DAO_PROPOSAL_VOTE = "dao_proposal_vote"
    DAO_PROPOSAL_CONCLUDE = "dao_proposal_conclude"
    DAO_PROPOSAL_EVALUATION = "dao_proposal_evaluation"
    DAO_TWEET = "dao_tweet"
    TWEET = "tweet"
    DISCORD = "discord"
    AGENT_ACCOUNT_DEPLOY = "agent_account_deploy"
    PROPOSAL_EMBEDDING = "proposal_embedding"
    CHAIN_STATE_MONITOR = "chain_state_monitor"

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
        self._start_time: Optional[float] = None

    @property
    def task_name(self) -> str:
        """Get the task name for logging purposes."""
        return self.__class__.__name__

    def _log_task_start(self) -> None:
        """Log task start with standard format."""
        import time

        self._start_time = time.time()
        logger.debug(f"Starting task: {self.task_name}")
        logger.debug(f"{self.task_name}: Configuration - {self.config}")

    def _log_task_completion(self, results: List[T]) -> None:
        """Log task completion with standard format and metrics."""
        import time

        if not self._start_time:
            return

        duration = time.time() - self._start_time
        success_count = len([r for r in results if r.success])
        failure_count = len([r for r in results if not r.success])

        logger.info(
            f"Completed task: {self.task_name} in {duration:.2f}s - "
            f"Success: {success_count}, Failures: {failure_count}"
        )

        if failure_count > 0:
            for result in results:
                if not result.success:
                    logger.error(f"{self.task_name} failure: {result.message}")

    @classmethod
    def get_result_class(cls) -> Type[RunnerResult]:
        """Get the result class for this task."""
        return cls.__orig_bases__[0].__args__[0]  # type: ignore

    async def validate(self, context: JobContext) -> bool:
        """Validate that the task can be executed.

        This method provides a validation pipeline:
        1. Configuration validation
        2. Prerequisites validation
        3. Task-specific validation
        """
        try:
            logger.debug(f"Starting validation for {self.task_name}")

            # Step 1: Configuration validation
            if not await self._validate_config(context):
                logger.warning(f"{self.task_name}: Configuration validation failed")
                return False

            # Step 2: Prerequisites validation
            if not await self._validate_prerequisites(context):
                logger.debug(f"{self.task_name}: Prerequisites validation failed")
                return False

            # Step 3: Task-specific validation
            if not await self._validate_task_specific(context):
                logger.debug(f"{self.task_name}: Task-specific validation failed")
                return False

            logger.debug(f"{self.task_name}: All validation checks passed")
            return True
        except Exception as e:
            logger.error(
                f"Error in validation for {self.task_name}: {str(e)}", exc_info=True
            )
            return False

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        return True

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites."""
        return True

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        return True

    async def execute(self, context: JobContext) -> List[T]:
        """Execute the task with given context."""
        self._log_task_start()
        try:
            results = await self._execute_impl(context)
            self._log_task_completion(results)
            return results
        except Exception as e:
            logger.error(f"Error executing {self.task_name}: {str(e)}", exc_info=True)
            result_class = self.get_result_class()
            return [
                result_class(
                    success=False, message=f"Error executing task: {str(e)}", error=e
                )
            ]

    @abstractmethod
    async def _execute_impl(self, context: JobContext) -> List[T]:
        """Implementation of task execution logic.
        This method should be implemented by subclasses."""
        pass
