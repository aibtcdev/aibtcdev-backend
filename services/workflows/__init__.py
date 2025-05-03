"""Workflows package for LangGraph-based workflows."""

# Base workflow components
from services.workflows.base import (
    BaseWorkflow,
    BaseWorkflowMixin,
    ExecutionError,
    LangGraphError,
    MessageContent,
    MessageProcessor,
    StateType,
    StreamingCallbackHandler,
    StreamingError,
    ValidationError,
)

# Remove all imports from deleted files and import from chat.py
from services.workflows.chat import (
    ChatService,
    ChatWorkflow,
    execute_chat_stream,
)
from services.workflows.planning_mixin import PlanningCapability

# Special purpose workflows
from services.workflows.proposal_evaluation import (
    ProposalEvaluationWorkflow,
    evaluate_and_vote_on_proposal,
    evaluate_proposal_only,
)

# Core messaging and streaming components
# Core ReAct workflow components
from services.workflows.tweet_analysis import (
    TweetAnalysisWorkflow,
    analyze_tweet,
)
from services.workflows.tweet_generator import (
    TweetGeneratorWorkflow,
    generate_dao_tweet,
)
from services.workflows.vector_mixin import (
    VectorRetrievalCapability,
    add_documents_to_vectors,
)
from services.workflows.web_search_mixin import WebSearchCapability

# Workflow service and factory
from services.workflows.workflow_service import (
    BaseWorkflowService,
    WorkflowBuilder,
    WorkflowFactory,
    WorkflowService,
    execute_workflow_stream,
)

__all__ = [
    # Base workflow foundation
    "BaseWorkflow",
    "BaseWorkflowMixin",
    "ExecutionError",
    "LangGraphError",
    "StateType",
    "StreamingError",
    "ValidationError",
    "VectorRetrievalCapability",
    # Workflow service layer
    "BaseWorkflowService",
    "WorkflowBuilder",
    "WorkflowFactory",
    "WorkflowService",
    "execute_workflow_stream",
    # Core messaging components
    "MessageContent",
    "MessageProcessor",
    "StreamingCallbackHandler",
    # Core ReAct workflow
    "LangGraphService",
    "ReactState",
    "ReactWorkflow",
    "execute_langgraph_stream",
    # Special purpose workflows
    "ProposalEvaluationWorkflow",
    "TweetAnalysisWorkflow",
    "TweetGeneratorWorkflow",
    "analyze_tweet",
    "evaluate_and_vote_on_proposal",
    "evaluate_proposal_only",
    "generate_dao_tweet",
    # Chat workflow
    "ChatService",
    "ChatWorkflow",
    "execute_chat_stream",
    # Mixins
    "PlanningCapability",
    "WebSearchCapability",
    "add_documents_to_vectors",
]
