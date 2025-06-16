from typing import List, Optional

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


class ComprehensiveEvaluationOutput(BaseModel):
    """Output model for comprehensive single-pass proposal evaluation."""

    # Core evaluation
    core_score: int = Field(description="Core context evaluation score (0-100)")
    core_flags: List[str] = Field(description="Core context critical issues")
    core_summary: str = Field(description="Core context evaluation summary")

    # Financial evaluation
    financial_score: int = Field(description="Financial evaluation score (0-100)")
    financial_flags: List[str] = Field(description="Financial critical issues")
    financial_summary: str = Field(description="Financial evaluation summary")

    # Historical evaluation
    historical_score: int = Field(
        description="Historical context evaluation score (0-100)"
    )
    historical_flags: List[str] = Field(
        description="Historical context critical issues"
    )
    historical_summary: str = Field(description="Historical context evaluation summary")
    sequence_analysis: str = Field(
        description="Analysis of proposal sequences and relationships"
    )

    # Social evaluation
    social_score: int = Field(description="Social context evaluation score (0-100)")
    social_flags: List[str] = Field(description="Social context critical issues")
    social_summary: str = Field(description="Social context evaluation summary")

    # Final decision
    final_score: int = Field(description="Final comprehensive evaluation score (0-100)")
    decision: str = Field(description="Final decision: Approve or Reject")
    explanation: str = Field(
        description="Comprehensive reasoning for the final decision"
    )

    # Overall flags from all evaluations
    all_flags: List[str] = Field(
        description="All critical issues identified across evaluations"
    )
