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


class ProposalSummarizationOutput(BaseModel):
    """Output model for proposal title and summary generation."""

    title: str = Field(
        description="Generated proposal title (max 100 characters)", max_length=100
    )
    summary: str = Field(
        description="Short summary of the proposal (2-3 sentences, max 500 characters)",
        max_length=500,
    )
