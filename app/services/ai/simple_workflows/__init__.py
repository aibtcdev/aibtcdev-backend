"""Simple Workflows - Simplified AI workflow implementations.

This package replaces the complex mixin-based workflow system with simple,
functional implementations that are easier to understand and maintain.

Key modules:
- orchestrator: Main public API facade
- evaluation: Comprehensive proposal evaluation
- metadata: Proposal metadata generation
- recommendation: Proposal recommendation generation
- processors/: Image and Twitter content processing
- llm: Simplified LLM wrapper utilities
- streaming: Minimal streaming callback handler
- prompts/: Centralized prompt management for all workflows
"""

from .orchestrator import (
    evaluate_proposal_strict,
    evaluate_proposal_comprehensive,
    generate_proposal_metadata,
    generate_proposal_recommendation,
)
from .tool_executor import (
    execute_workflow_stream,
    generate_dao_tweet,
    analyze_tweet,
)
from .network_school_evaluator import (
    evaluate_user_posts,
    NetworkSchoolEvaluationResult,
    PostEvaluation,
)

__all__ = [
    "evaluate_proposal_strict",
    "evaluate_proposal_comprehensive",
    "generate_proposal_metadata",
    "generate_proposal_recommendation",
    "execute_workflow_stream",
    "generate_dao_tweet",
    "analyze_tweet",
    "evaluate_user_posts",
    "NetworkSchoolEvaluationResult",
    "PostEvaluation",
]
