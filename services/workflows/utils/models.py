from typing import List

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
