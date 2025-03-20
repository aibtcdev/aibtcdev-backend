"""Workflows package for LangGraph-based workflows."""

# Base workflow components
from services.workflows.base import (
    BaseWorkflow,
    BaseWorkflowMixin,
    ExecutionError,
    LangGraphError,
    PlanningCapability,
    StateType,
    StreamingError,
    ValidationError,
    VectorRetrievalCapability,
)

# Enhanced ReAct workflow variants
from services.workflows.preplan_react import (
    PreplanLangGraphService,
    PreplanReactWorkflow,
    PreplanState,
    execute_preplan_react_stream,
)

# Special purpose workflows
from services.workflows.proposal_evaluation import (
    ProposalEvaluationWorkflow,
    evaluate_and_vote_on_proposal,
    evaluate_proposal_only,
)

# Core messaging and streaming components
# Core ReAct workflow components
from services.workflows.react import (
    LangGraphService,
    MessageContent,
    MessageProcessor,
    ReactState,
    ReactWorkflow,
    StreamingCallbackHandler,
    execute_langgraph_stream,
)
from services.workflows.tweet_analysis import (
    TweetAnalysisWorkflow,
    analyze_tweet,
)
from services.workflows.tweet_generator import (
    TweetGeneratorWorkflow,
    generate_dao_tweet,
)
from services.workflows.vector_react import (
    VectorLangGraphService,
    VectorReactState,
    VectorReactWorkflow,
    add_documents_to_vectors,
    execute_vector_langgraph_stream,
)

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
    "PlanningCapability",
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
    # PrePlan ReAct workflow
    "PreplanLangGraphService",
    "PreplanReactWorkflow",
    "PreplanState",
    "execute_preplan_react_stream",
    # Vector ReAct workflow
    "VectorLangGraphService",
    "VectorReactState",
    "VectorReactWorkflow",
    "add_documents_to_vectors",
    "execute_vector_langgraph_stream",
    # Special purpose workflows
    "ProposalEvaluationWorkflow",
    "TweetAnalysisWorkflow",
    "TweetGeneratorWorkflow",
    "analyze_tweet",
    "evaluate_and_vote_on_proposal",
    "evaluate_proposal_only",
    "generate_dao_tweet",
]
