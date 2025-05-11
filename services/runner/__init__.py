"""Runner module for executing tasks such as DAO processing and Twitter interactions."""

from services.runner.base import BaseTask, JobContext, JobType
from services.runner.job_manager import JobConfig, JobManager
from services.runner.registry import JobRegistry, execute_runner_job
from services.runner.tasks.agent_account_deployer import (
    AgentAccountDeployerTask,
    agent_account_deployer,
)
from services.runner.tasks.chain_state_monitor import (
    ChainStateMonitorTask,
    chain_state_monitor,
)
from services.runner.tasks.dao_proposal_concluder import (
    DAOProposalConcluderTask,
    dao_proposal_concluder,
)
from services.runner.tasks.dao_proposal_evaluation import (
    DAOProposalEvaluationTask,
    dao_proposal_evaluation,
)
from services.runner.tasks.dao_proposal_voter import (
    DAOProposalVoterTask,
    dao_proposal_voter,
)
from services.runner.tasks.dao_task import DAOTask, dao_task
from services.runner.tasks.dao_tweet_task import DAOTweetTask, dao_tweet_task
from services.runner.tasks.proposal_embedder import (
    ProposalEmbedderTask,
    proposal_embedder,
)
from services.runner.tasks.tweet_task import TweetTask, tweet_task

# Register tasks with the registry
JobRegistry.register(JobType.DAO, DAOTask)
JobRegistry.register(JobType.DAO_PROPOSAL_VOTE, DAOProposalVoterTask)
JobRegistry.register(JobType.DAO_PROPOSAL_CONCLUDE, DAOProposalConcluderTask)
JobRegistry.register(JobType.DAO_PROPOSAL_EVALUATION, DAOProposalEvaluationTask)
JobRegistry.register(JobType.DAO_TWEET, DAOTweetTask)
JobRegistry.register(JobType.TWEET, TweetTask)
JobRegistry.register(JobType.AGENT_ACCOUNT_DEPLOY, AgentAccountDeployerTask)
JobRegistry.register(JobType.PROPOSAL_EMBEDDING, ProposalEmbedderTask)
JobRegistry.register(JobType.CHAIN_STATE_MONITOR, ChainStateMonitorTask)

__all__ = [
    "BaseTask",
    "JobContext",
    "JobRegistry",
    "JobType",
    "JobConfig",
    "JobManager",
    "DAOTask",
    "dao_task",
    "DAOProposalVoterTask",
    "dao_proposal_voter",
    "DAOTweetTask",
    "dao_tweet_task",
    "TweetTask",
    "tweet_task",
    "execute_runner_job",
    "DAOProposalConcluderTask",
    "dao_proposal_concluder",
    "DAOProposalEvaluationTask",
    "dao_proposal_evaluation",
    "AgentAccountDeployerTask",
    "agent_account_deployer",
    "ProposalEmbedderTask",
    "proposal_embedder",
    "ChainStateMonitorTask",
    "chain_state_monitor",
]
