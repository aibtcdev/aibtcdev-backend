from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class AgentAccountDeployInput(BaseModel):
    """Input schema for deploying an agent account contract."""

    owner_address: str = Field(
        ...,
        description="Stacks address of the wallet owner",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
    )
    agent_address: str = Field(
        ...,
        description="Stacks address of the agent",
        example="ST2CY5V39NHDPWSXMW9QDT3HC3GD6Q6XX4CFRK9AG",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    dao_token_dex_contract: str = Field(
        ...,
        description="Contract principal of the DAO token DEX",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token-dex",
    )
    save_to_file: bool = Field(
        False,
        description="Whether to save the contract to a file",
    )


class AgentAccountBuyAssetInput(BaseModel):
    """Input schema for buying assets through an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for buying",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )
    faktory_dex_contract: str = Field(
        ...,
        description="Contract principal of the Faktory DEX to buy from",
        example="ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K.facey-faktory-dex",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to buy",
        example="ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K.facey-faktory",
    )
    amount: int = Field(
        ...,
        description="Amount of the asset to buy (in base units)",
        example=1000,
        gt=0,
    )


class AgentAccountVoteInput(BaseModel):
    """Input schema for voting on action proposals through an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for voting",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )
    voting_contract: str = Field(
        ...,
        description="Contract principal of the voting contract",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to vote on",
        example=1,
        gt=0,
    )
    vote: bool = Field(
        ...,
        description="Vote choice (true for yes, false for no)",
        example=True,
    )


class AgentAccountCreateActionProposalInput(BaseModel):
    """Input schema for creating action proposals through an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for creating proposal",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )
    voting_contract: str = Field(
        ...,
        description="Contract principal of the voting contract",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    action_contract: str = Field(
        ...,
        description="Contract principal of the action to be executed",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-send-message",
    )
    parameters_hex: str = Field(
        ...,
        description="Hex string containing the parameters for the action",
        example="68656c6c6f20776f726c64",
    )
    memo: Optional[str] = Field(
        None,
        description="Optional memo for the proposal",
        example="My proposal description",
    )


class AgentAccountDeployTool(BaseTool):
    name: str = "agent_account_deploy"
    description: str = (
        "Deploy a new agent account contract with specified owner and agent addresses. "
        "Returns the deployed contract address and transaction ID."
    )
    args_schema: Type[BaseModel] = AgentAccountDeployInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None
    seed_phrase: Optional[str] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        seed_phrase: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id
        self.seed_phrase = seed_phrase

    def _deploy(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        save_to_file: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy agent account."""
        if self.seed_phrase is None and self.wallet_id is None:
            return {
                "success": False,
                "message": "Either seed phrase or wallet ID is required",
                "data": None,
            }

        args = [
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            str(save_to_file).lower(),
        ]

        # Use seed phrase if available, otherwise fall back to wallet_id
        if self.seed_phrase:
            return BunScriptRunner.bun_run_with_seed_phrase(
                self.seed_phrase,
                "aibtc-cohort-0/contract-tools",
                "deploy-agent-account.ts",
                *args,
            )
        else:
            return BunScriptRunner.bun_run(
                self.wallet_id,
                "aibtc-cohort-0/contract-tools",
                "deploy-agent-account.ts",
                *args,
            )

    def _run(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        save_to_file: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy agent account."""
        return self._deploy(
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            save_to_file,
            **kwargs,
        )

    async def _arun(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        save_to_file: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            save_to_file,
            **kwargs,
        )


class AgentAccountBuyAssetTool(BaseTool):
    name: str = "agent_account_buy_asset"
    description: str = (
        "Buy assets through an agent account contract using a Faktory DEX. "
        "Returns the transaction ID and details of the asset purchase."
    )
    args_schema: Type[BaseModel] = AgentAccountBuyAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _buy_asset(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to buy assets through agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            str(amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "acct-buy-asset.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to buy assets through agent account."""
        return self._buy_asset(
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            amount,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._buy_asset(
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            amount,
            **kwargs,
        )


class AgentAccountVoteTool(BaseTool):
    name: str = "agent_account_vote"
    description: str = (
        "Vote on action proposals through an agent account contract. "
        "Returns the transaction ID and details of the vote."
    )
    args_schema: Type[BaseModel] = AgentAccountVoteInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _vote(
        self,
        agent_account_contract: str,
        voting_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on action proposals through agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            voting_contract,
            str(proposal_id),
            str(vote).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "vote-on-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        voting_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on action proposals through agent account."""
        return self._vote(
            agent_account_contract,
            voting_contract,
            proposal_id,
            vote,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        voting_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._vote(
            agent_account_contract,
            voting_contract,
            proposal_id,
            vote,
            **kwargs,
        )


class AgentAccountCreateActionProposalTool(BaseTool):
    name: str = "agent_account_create_action_proposal"
    description: str = (
        "Create action proposals through an agent account contract. "
        "Returns the transaction ID and details of the created proposal."
    )
    args_schema: Type[BaseModel] = AgentAccountCreateActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _create_action_proposal(
        self,
        agent_account_contract: str,
        voting_contract: str,
        dao_token_contract: str,
        action_contract: str,
        parameters_hex: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create action proposals through agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            voting_contract,
            dao_token_contract,
            action_contract,
            parameters_hex,
        ]

        # Add memo if provided
        if memo:
            args.append(memo)

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "create-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        voting_contract: str,
        dao_token_contract: str,
        action_contract: str,
        parameters_hex: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create action proposals through agent account."""
        return self._create_action_proposal(
            agent_account_contract,
            voting_contract,
            dao_token_contract,
            action_contract,
            parameters_hex,
            memo,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        voting_contract: str,
        dao_token_contract: str,
        action_contract: str,
        parameters_hex: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._create_action_proposal(
            agent_account_contract,
            voting_contract,
            dao_token_contract,
            action_contract,
            parameters_hex,
            memo,
            **kwargs,
        )
