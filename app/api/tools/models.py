from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.backend.models import UUID


class FaktoryBuyTokenRequest(BaseModel):
    """Request body for executing a Faktory buy order."""

    btc_amount: str = Field(
        ...,
        description="Amount of BTC to spend on the purchase in standard units (e.g. 0.0004 = 0.0004 BTC or 40000 sats)",
        example="0.0004",
    )
    dao_token_dex_contract_address: str = Field(
        ...,
        description="Contract principal where the DAO token is listed",
        example="SP1234567890ABCDEF.dao-token-dex",
    )
    slippage: Optional[str] = Field(
        default="15",
        description="Slippage tolerance in basis points (default: 15, which is 0.15%)",
        example="15",
    )


class ProposeSendMessageRequest(BaseModel):
    """Request body for proposing a DAO action to send a message via agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for creating the proposal.",
        example="SP1234567890ABCDEF.agent-account-v1",
    )
    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        example="SP1234567890ABCDEF.dao-action-proposals-voting",
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes sending a message.",
        example="SP1234567890ABCDEF.proposal-send-message-v1",
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting.",
        example="SP1234567890ABCDEF.dao-token",
    )
    message: str = Field(
        ...,
        description="Message to be sent through the DAO proposal system.",
        example="This is a proposal message to be sent through the DAO governance system.",
    )
    memo: Optional[str] = Field(
        None,
        description="Optional memo to include with the proposal.",
        example="Monthly governance update",
    )


class VetoActionProposalRequest(BaseModel):
    """Request body for vetoing a DAO action proposal."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        example="SP1234567890ABCDEF.dao-action-proposals-voting",
    )
    proposal_id: str = Field(
        ...,
        description="ID of the proposal to veto.",
        example="12345678-1234-1234-1234-123456789abc",
    )


class AgentAccountApproveContractRequest(BaseModel):
    """Request body for approving a contract for use with an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account",
        example="SP1234567890ABCDEF.agent-account-v1",
    )
    contract_to_approve: str = Field(
        ...,
        description="The contract principal to approve",
        example="SP1234567890ABCDEF.dao-contract-to-approve",
    )


class FundWalletFaucetRequest(BaseModel):
    """Request body for funding wallet with testnet STX tokens."""

    model_config = {
        "json_schema_extra": {
            "example": {},
            "description": "No parameters needed as the tool uses wallet_id from initialization",
        }
    }

    pass  # No parameters needed as the tool uses wallet_id from initialization


class FundSbtcFaucetRequest(BaseModel):
    """Request body for requesting testnet sBTC from Faktory faucet."""

    model_config = {
        "json_schema_extra": {
            "example": {},
            "description": "No parameters needed as the tool uses wallet_id from initialization",
        }
    }

    pass  # No parameters needed as the tool uses wallet_id from initialization


class ProposalRecommendationRequest(BaseModel):
    """Request body for getting a proposal recommendation."""

    dao_id: UUID = Field(
        ...,
        description="The ID of the DAO to generate a proposal recommendation for.",
        example="12345678-1234-1234-1234-123456789abc",
    )
    focus_area: Optional[str] = Field(
        default="general improvement",
        description="Specific area of focus for the recommendation (e.g., 'community growth', 'technical development', 'partnerships')",
        example="community growth",
    )
    specific_needs: Optional[str] = Field(
        default="",
        description="Any specific needs or requirements to consider in the recommendation",
        example="Need to increase member engagement and create more incentive programs",
    )
    model_name: Optional[str] = Field(
        default="x-ai/grok-4",
        description="LLM model to use for generation (e.g., 'gpt-4.1', 'gpt-4o', 'gpt-3.5-turbo')",
        example="x-ai/grok-4",
    )
    temperature: Optional[float] = Field(
        default=0.1,
        description="Temperature for LLM generation (0.0-2.0). Lower = more focused, Higher = more creative",
        ge=0.0,
        le=2.0,
        example=0.1,
    )


class ComprehensiveEvaluationRequest(BaseModel):
    """Request body for comprehensive proposal evaluation."""

    proposal_id: str = Field(
        ...,
        description="Unique identifier for the proposal being evaluated.",
        example="12345678-1234-1234-1234-123456789abc",
    )
    proposal_content: Optional[str] = Field(
        None,
        description="Optional proposal content to override the default proposal content.",
        example="This is a proposal to implement a new governance mechanism for the DAO.",
    )
    dao_id: Optional[UUID] = Field(
        None,
        description="Optional DAO ID for context.",
        example="12345678-1234-1234-1234-123456789abc",
    )
    custom_system_prompt: Optional[str] = Field(
        None,
        description="Optional custom system prompt to override the default evaluation prompt.",
        example="You are an expert DAO governance evaluator. Analyze this proposal for technical feasibility and community impact.",
    )
    custom_user_prompt: Optional[str] = Field(
        None,
        description="Optional custom user prompt to override the default evaluation instructions.",
        example="Please evaluate this proposal's alignment with our DAO's mission and values.",
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional configuration for the evaluation agent.",
        example={"model": "gpt-4", "temperature": 0.1},
    )


class DefaultPromptsResponse(BaseModel):
    """Response body for default evaluation prompts."""

    system_prompt: str = Field(
        ...,
        description="The default system prompt used for comprehensive evaluation.",
        example="You are an expert DAO governance evaluator with deep knowledge of blockchain governance.",
    )
    user_prompt_template: str = Field(
        ...,
        description="The default user prompt template used for comprehensive evaluation.",
        example="Please evaluate the following proposal: {proposal_content}",
    )


# Response models for swagger documentation


class ToolResponse(BaseModel):
    """Standard response model for tool operations."""

    success: bool = Field(
        ..., description="Whether the operation was successful", example=True
    )
    message: str = Field(
        ...,
        description="Human-readable message about the operation result",
        example="Operation completed successfully",
    )
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional data returned by the operation",
        example={"transaction_id": "0x1234567890abcdef"},
    )
    error: Optional[str] = Field(
        None, description="Error message if operation failed", example=None
    )


class TwitterEmbedResponse(BaseModel):
    """Response model for Twitter embed data."""

    html: str = Field(
        ...,
        description="HTML code for embedding the tweet",
        example='<blockquote class="twitter-tweet">...</blockquote>',
    )
    url: str = Field(
        ...,
        description="URL of the tweet",
        example="https://twitter.com/user/status/1234567890",
    )
    author_name: str = Field(
        ..., description="Name of the tweet author", example="John Doe"
    )
    author_url: str = Field(
        ...,
        description="URL of the author's profile",
        example="https://twitter.com/johndoe",
    )
    width: int = Field(..., description="Width of the embed", example=550)
    height: Optional[int] = Field(None, description="Height of the embed", example=400)
    type: str = Field(..., description="Type of embed", example="rich")
    version: str = Field(..., description="oEmbed version", example="1.0")
