from .base import BaseTask, JobContext, JobType, RunnerConfig, RunnerResult
from .registry import JobRegistry, execute_runner_job
from .tasks.dao_task import DAOProcessingResult, DAOTask
from .tasks.tweet_task import TweetProcessingResult, TweetTask

# Register tasks
JobRegistry.register(JobType.DAO, DAOTask)
JobRegistry.register(JobType.TWEET, TweetTask)

__all__ = [
    "BaseTask",
    "JobContext",
    "JobType",
    "RunnerConfig",
    "RunnerResult",
    "JobRegistry",
    "execute_runner_job",
    "DAOProcessingResult",
    "DAOTask",
    "TweetProcessingResult",
    "TweetTask",
]
