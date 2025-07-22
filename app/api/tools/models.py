from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.backend.models import UUID


class FaktoryBuyTokenRequest(BaseModel):
    """Request body for executing a Faktory buy order."""

    btc_amount: str = Field(
        ...,
        description="Amount of BTC to spend on the purchase in standard units (e.g. 0.0004 = 0.0004 BTC or 40000 sats)",
    )
    dao_token_dex_contract_address: str = Field(
        ..., description="Contract principal where the DAO token is listed"
    )
    slippage: Optional[str] = Field(
        default="15",
        description="Slippage tolerance in basis points (default: 15, which is 0.15%)",
    )


class ProposeSendMessageRequest(BaseModel):
    """Request body for proposing a DAO action to send a message via agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for creating the proposal.",
    )
    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes sending a message.",
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting.",
    )
    message: str = Field(
        ...,
        description="Message to be sent through the DAO proposal system.",
    )
    memo: Optional[str] = Field(
        None,
        description="Optional memo to include with the proposal.",
    )


class VetoActionProposalRequest(BaseModel):
    """Request body for vetoing a DAO action proposal."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
    )
    proposal_id: str = Field(
        ...,
        description="ID of the proposal to veto.",
    )


class AgentAccountApproveContractRequest(BaseModel):
    """Request body for approving a contract for use with an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account",
    )
    contract_to_approve: str = Field(
        ...,
        description="The contract principal to approve",
    )
    approval_type: str = Field(
        ..., description="Type of contract approval (e.g., 'VOTING', 'SWAP', 'TOKEN')"
    )


class FundWalletFaucetRequest(BaseModel):
    """Request body for funding wallet with testnet STX tokens."""

    pass  # No parameters needed as the tool uses wallet_id from initialization


class FundSbtcFaucetRequest(BaseModel):
    """Request body for requesting testnet sBTC from Faktory faucet."""

    pass  # No parameters needed as the tool uses wallet_id from initialization


class ProposalRecommendationRequest(BaseModel):
    """Request body for getting a proposal recommendation."""

    dao_id: UUID = Field(
        ...,
        description="The ID of the DAO to generate a proposal recommendation for.",
    )
    focus_area: Optional[str] = Field(
        default="general improvement",
        description="Specific area of focus for the recommendation (e.g., 'community growth', 'technical development', 'partnerships')",
    )
    specific_needs: Optional[str] = Field(
        default="",
        description="Any specific needs or requirements to consider in the recommendation",
    )
    model_name: Optional[str] = Field(
        default="x-ai/grok-4",
        description="LLM model to use for generation (e.g., 'gpt-4.1', 'gpt-4o', 'gpt-3.5-turbo')",
    )
    temperature: Optional[float] = Field(
        default=0.1,
        description="Temperature for LLM generation (0.0-2.0). Lower = more focused, Higher = more creative",
        ge=0.0,
        le=2.0,
    )


class ComprehensiveEvaluationRequest(BaseModel):
    """Request body for comprehensive proposal evaluation."""

    proposal_id: str = Field(
        ...,
        description="Unique identifier for the proposal being evaluated.",
    )
    proposal_content: Optional[str] = Field(
        None,
        description="Optional proposal content to override the default proposal content.",
    )
    dao_id: Optional[UUID] = Field(
        None,
        description="Optional DAO ID for context.",
    )
    custom_system_prompt: Optional[str] = Field(
        None,
        description="Optional custom system prompt to override the default evaluation prompt.",
    )
    custom_user_prompt: Optional[str] = Field(
        None,
        description="Optional custom user prompt to override the default evaluation instructions.",
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional configuration for the evaluation agent.",
    )


class DefaultPromptsResponse(BaseModel):
    """Response body for default evaluation prompts."""

    system_prompt: str = Field(
        ...,
        description="The default system prompt used for comprehensive evaluation.",
    )
    user_prompt_template: str = Field(
        ...,
        description="The default user prompt template used for comprehensive evaluation.",
    )
