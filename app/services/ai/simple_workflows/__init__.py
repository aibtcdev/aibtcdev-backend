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
"""

from .orchestrator import (
    evaluate_proposal_comprehensive,
    generate_proposal_metadata,
    generate_proposal_recommendation,
)
from .tool_executor import (
    execute_workflow_stream,
    generate_dao_tweet,
    analyze_tweet,
)

__all__ = [
    "evaluate_proposal_comprehensive",
    "generate_proposal_metadata",
    "generate_proposal_recommendation",
    "execute_workflow_stream",
    "generate_dao_tweet",
    "analyze_tweet",
]
