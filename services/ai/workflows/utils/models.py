from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AgentOutput(BaseModel):
    """Output model for agent evaluations."""

    score: int = Field(description="Score from 0-100")
    flags: List[str] = Field(description="Critical issues flagged")
    summary: str = Field(description="Summary of findings")


class FinalOutput(BaseModel):
    """Output model for the final evaluation decision."""

    score: int = Field(description="Final evaluation score")
    decision: str = Field(description="Approve or Reject")
    explanation: str = Field(description="Reasoning for decision")


class ProposalEvaluationOutput(BaseModel):
    """Output model for proposal evaluation."""

    approve: bool = Field(
        description="Decision: true to approve (vote FOR), false to reject (vote AGAINST)"
    )
    confidence_score: float = Field(
        description="Confidence score for the decision (0.0-1.0)"
    )
    reasoning: str = Field(description="The reasoning behind the evaluation decision")


class ProposalRecommendationOutput(BaseModel):
    """Output model for proposal recommendations."""

    title: str = Field(description="Recommended proposal title")
    content: str = Field(description="Recommended proposal content/description")
    rationale: str = Field(
        description="Explanation of why this proposal is recommended"
    )
    priority: str = Field(
        description="Priority level: high, medium, low", pattern="^(high|medium|low)$"
    )
    estimated_impact: str = Field(description="Expected impact on the DAO")
    suggested_action: Optional[str] = Field(
        description="Specific action or next steps if applicable", default=None
    )


class ProposalMetadataOutput(BaseModel):
    """Output model for proposal metadata generation."""

    title: str = Field(
        description="Generated proposal title (max 100 characters)", max_length=100
    )
    summary: str = Field(
        description="Short summary of the proposal (2-3 sentences, max 500 characters)",
        max_length=500,
    )
    tags: List[str] = Field(
        description="Array of 3-5 relevant tags that categorize the proposal content",
        min_length=3,
        max_length=5,
    )


class EvaluationCategory(BaseModel):
    """Model for a single evaluation category."""

    category: str = Field(description="Category name")
    score: int = Field(description="Score from 1-100", ge=1, le=100)
    weight: float = Field(
        description="Weight of this category in final decision (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    reasoning: List[str] = Field(
        description="Reasoning in 3 or less bullet points", max_length=3
    )


class ComprehensiveEvaluationOutput(BaseModel):
    """Output model for comprehensive single-pass proposal evaluation with dynamic categories."""

    categories: List[EvaluationCategory] = Field(
        description="List of evaluation categories with scores, weights, and reasoning"
    )
    final_score: int = Field(
        description="Final comprehensive evaluation score (1-100)", ge=1, le=100
    )
    decision: bool = Field(
        description="Final decision: True to approve (vote FOR), false to reject (vote AGAINST)"
    )
    explanation: str = Field(
        description="Comprehensive reasoning for the final decision"
    )
    flags: List[str] = Field(
        description="All critical issues identified across evaluations"
    )
    summary: str = Field(description="Summary of the evaluation")


class ComprehensiveEvaluatorAgentProcessOutput(BaseModel):
    """Output model for the ComprehensiveEvaluatorAgent's process method."""

    categories: List[EvaluationCategory] = Field(
        description="List of evaluation categories with scores, weights, and reasoning"
    )
    final_score: int = Field(
        description="Final comprehensive evaluation score (1-100)", ge=1, le=100
    )
    decision: bool = Field(
        description="Final decision: True to approve (vote FOR), false to reject (vote AGAINST)"
    )
    explanation: str = Field(
        description="Comprehensive reasoning for the final decision"
    )
    flags: List[str] = Field(
        description="All critical issues identified across evaluations"
    )
    summary: str = Field(description="Summary of the evaluation")
    token_usage: Dict[str, Union[int, str]] = Field(
        default_factory=dict, description="Token usage statistics for the evaluation"
    )
    images_processed: int = Field(
        default=0, description="Number of images processed during evaluation"
    )
