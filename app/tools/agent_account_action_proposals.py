from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.bun import BunScriptRunner


class AgentAccountCreateActionProposalInput(BaseModel):
    """Input schema for creating action proposals through an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for creating proposal",
        examples=[
            "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-acct-ST1PQ-PGZGM-ST35K-VM3QA"
        ],
    )
    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal of the voting contract",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    action_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action to be executed",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-send-message"
        ],
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        examples=["ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token"],
    )
    message_to_send: str = Field(
        ...,
        description="The message to send for the action",
        examples=["This is my message."],
    )
    memo: Optional[str] = Field(
        None,
        description="Optional memo for the proposal",
        examples=["This is my memo."],
    )


class AgentAccountCreateActionProposalTool(BaseTool):
    name: str = "agent_account_create_action_proposal"
    description: str = (
        "Create an action proposal through an agent account contract. "
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

    def _run_script(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        action_contract_to_execute: str,
        dao_token_contract: str,
        message_to_send: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create an action proposal through an agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            dao_action_proposal_voting_contract,
            action_contract_to_execute,
            dao_token_contract,
            message_to_send,
        ]

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
        dao_action_proposal_voting_contract: str,
        action_contract_to_execute: str,
        dao_token_contract: str,
        message_to_send: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(
            agent_account_contract,
            dao_action_proposal_voting_contract,
            action_contract_to_execute,
            dao_token_contract,
            message_to_send,
            memo,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        action_contract_to_execute: str,
        dao_token_contract: str,
        message_to_send: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            agent_account_contract,
            dao_action_proposal_voting_contract,
            action_contract_to_execute,
            dao_token_contract,
            message_to_send,
            memo,
            **kwargs,
        )


class AgentAccountVoteOnActionProposalInput(BaseModel):
    """Input schema for voting on action proposals through an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for voting",
        examples=[
            "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-acct-ST1PQ-PGZGM-ST35K-VM3QA"
        ],
    )
    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal of the voting contract",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to vote on",
        examples=[13],
        gt=0,
    )
    vote: bool = Field(
        ...,
        description="Vote choice (true for yes, false for no)",
        examples=[True],
    )


class AgentAccountVoteOnActionProposalTool(BaseTool):
    name: str = "agent_account_vote_on_action_proposal"
    description: str = (
        "Vote on an action proposal through an agent account contract. "
        "Returns the transaction ID and details of the vote."
    )
    args_schema: Type[BaseModel] = AgentAccountVoteOnActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _run_script(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal through an agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            dao_action_proposal_voting_contract,
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
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(
            agent_account_contract,
            dao_action_proposal_voting_contract,
            proposal_id,
            vote,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            agent_account_contract,
            dao_action_proposal_voting_contract,
            proposal_id,
            vote,
            **kwargs,
        )


class AgentAccountVetoActionProposalInput(BaseModel):
    """Input schema for vetoing an action proposal through an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for vetoing",
        examples=[
            "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-acct-ST1PQ-PGZGM-ST35K-VM3QA"
        ],
    )
    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal of the voting contract",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to veto",
        examples=[1],
        gt=0,
    )


class AgentAccountVetoActionProposalTool(BaseTool):
    name: str = "agent_account_veto_action_proposal"
    description: str = (
        "Veto an action proposal through an agent account contract. "
        "Returns the transaction ID and details of the veto."
    )
    args_schema: Type[BaseModel] = AgentAccountVetoActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _run_script(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to veto an action proposal through an agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            dao_action_proposal_voting_contract,
            str(proposal_id),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "veto-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(
            agent_account_contract,
            dao_action_proposal_voting_contract,
            proposal_id,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            agent_account_contract,
            dao_action_proposal_voting_contract,
            proposal_id,
            **kwargs,
        )


class AgentAccountConcludeActionProposalInput(BaseModel):
    """Input schema for concluding action proposals through an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for concluding",
        examples=[
            "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-acct-ST1PQ-PGZGM-ST35K-VM3QA"
        ],
    )
    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal of the voting contract",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    action_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action to be executed",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-send-message"
        ],
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        examples=["ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token"],
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to conclude",
        examples=[13],
        gt=0,
    )


class AgentAccountConcludeActionProposalTool(BaseTool):
    name: str = "agent_account_conclude_action_proposal"
    description: str = (
        "Conclude an action proposal through an agent account contract. "
        "Returns the transaction ID and details of the conclusion."
    )
    args_schema: Type[BaseModel] = AgentAccountConcludeActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _run_script(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        action_contract_to_execute: str,
        dao_token_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude an action proposal through an agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            dao_action_proposal_voting_contract,
            action_contract_to_execute,
            dao_token_contract,
            str(proposal_id),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "conclude-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        action_contract_to_execute: str,
        dao_token_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(
            agent_account_contract,
            dao_action_proposal_voting_contract,
            action_contract_to_execute,
            dao_token_contract,
            proposal_id,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        dao_action_proposal_voting_contract: str,
        action_contract_to_execute: str,
        dao_token_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            agent_account_contract,
            dao_action_proposal_voting_contract,
            action_contract_to_execute,
            dao_token_contract,
            proposal_id,
            **kwargs,
        )
