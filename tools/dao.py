from .bun import BunScriptRunner
from backend.models import UUID
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Type, Union


class DaoBaseTool(BaseTool):
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id


class DAOBaseInput(BaseModel):
    """Base input schema for DAO tools."""

    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")


class CoreContractInput(DAOBaseInput):
    """Input schema for core proposal contract-related tools."""

    core_proposals_contract: str = Field(
        ...,
        description="The core proposals contract address and name (e.g. ST1234.my-core-proposals)",
    )


class CoreProposalContractsInput(CoreContractInput):
    """Input schema for core proposal operations requiring both contracts."""

    proposal_contract: str = Field(
        ...,
        description="The proposal contract address and name (e.g. ST1234.my-proposal)",
    )


class CoreVoteInput(CoreProposalContractsInput):
    """Input schema for core proposal voting."""

    for_vote: bool = Field(
        ..., description="True for voting in favor, False for voting against"
    )


class ActionProposalInput(DAOBaseInput):
    """Input schema for action proposal-related tools."""

    action_proposals_contract: str = Field(
        ...,
        description="The action proposals contract address and name (e.g. ST1234.my-action-proposals)",
    )
    proposal_id: int = Field(..., description="The numeric ID of the action proposal")


class ActionVoteInput(ActionProposalInput):
    """Input schema for action proposal voting."""

    amount: str = Field(..., description="Amount of voting power to use")
    for_vote: bool = Field(
        ..., description="True for voting in favor, False for voting against"
    )


class BuyTokenInput(DAOBaseInput):
    """Input schema for buying tokens from the DEX."""

    dex_contract: str = Field(
        ..., description="The DEX contract address and name (e.g. ST1234.token-dex)"
    )
    token_contract: str = Field(
        ..., description="The token contract address and name (e.g. ST1234.token)"
    )
    stx_amount: str = Field(..., description="Amount of STX to spend on tokens")


# Core Proposal Tools
class CoreGetLinkedVotingContractsTool(DaoBaseTool):
    name: str = "dao_core_get_linked_voting_contracts"
    description: str = "Get the linked voting contracts for core proposals"
    args_schema: Type[BaseModel] = CoreContractInput
    return_direct: bool = False

    def _deploy(self, core_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get linked voting contracts."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/core-proposals/get-linked-voting-contracts.ts",
            core_proposals_contract,
        )

    def _run(self, core_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get linked voting contracts."""
        return self._deploy(core_proposals_contract, **kwargs)

    async def _arun(self, core_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(core_proposals_contract, **kwargs)


class CoreCreateProposalTool(DaoBaseTool):
    name: str = "dao_core_create_proposal"
    description: str = "Create a new core proposal"
    args_schema: Type[BaseModel] = CoreProposalContractsInput
    return_direct: bool = False

    def _deploy(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to create a proposal."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/core-proposals/create-proposal.ts",
            core_proposals_contract,
            proposal_contract,
        )

    def _run(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to create a proposal."""
        return self._deploy(core_proposals_contract, proposal_contract, **kwargs)

    async def _arun(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(core_proposals_contract, proposal_contract, **kwargs)


class CoreGetProposalTool(DaoBaseTool):
    name: str = "dao_core_get_proposal"
    description: str = "Get details of a core proposal"
    args_schema: Type[BaseModel] = CoreProposalContractsInput
    return_direct: bool = False

    def _deploy(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to get proposal details."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/core-proposals/get-proposal.ts",
            core_proposals_contract,
            proposal_contract,
        )

    def _run(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to get proposal details."""
        return self._deploy(core_proposals_contract, proposal_contract, **kwargs)

    async def _arun(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(core_proposals_contract, proposal_contract, **kwargs)


class CoreGetTotalVotesTool(DaoBaseTool):
    name: str = "dao_core_get_total_votes"
    description: str = "Get total votes for a core proposal"
    args_schema: Type[BaseModel] = CoreProposalContractsInput
    return_direct: bool = False

    def _deploy(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to get total votes."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/core-proposals/get-total-votes.ts",
            core_proposals_contract,
            proposal_contract,
        )

    def _run(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to get total votes."""
        return self._deploy(core_proposals_contract, proposal_contract, **kwargs)

    async def _arun(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(core_proposals_contract, proposal_contract, **kwargs)


class CoreGetVotingPowerTool(DaoBaseTool):
    name: str = "dao_core_get_voting_power"
    description: str = "Get voting power for core proposals"
    args_schema: Type[BaseModel] = CoreContractInput
    return_direct: bool = False

    def _deploy(self, core_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get voting power."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/core-proposals/get-voting-power.ts",
            core_proposals_contract,
        )

    def _run(self, core_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get voting power."""
        return self._deploy(core_proposals_contract, **kwargs)

    async def _arun(self, core_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(core_proposals_contract, **kwargs)


class CoreVoteOnProposalTool(DaoBaseTool):
    name: str = "dao_core_vote_on_proposal"
    description: str = "Vote on a core proposal"
    args_schema: Type[BaseModel] = CoreVoteInput
    return_direct: bool = False

    def _deploy(
        self,
        core_proposals_contract: str,
        proposal_contract: str,
        for_vote: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to vote on a proposal."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/core-proposals/vote-on-proposal.ts",
            core_proposals_contract,
            proposal_contract,
            str(for_vote).lower(),
        )

    def _run(
        self,
        core_proposals_contract: str,
        proposal_contract: str,
        for_vote: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to vote on a proposal."""
        return self._deploy(
            core_proposals_contract, proposal_contract, for_vote, **kwargs
        )

    async def _arun(
        self,
        core_proposals_contract: str,
        proposal_contract: str,
        for_vote: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            core_proposals_contract, proposal_contract, for_vote, **kwargs
        )


class CoreConcludeProposalTool(DaoBaseTool):
    name: str = "dao_core_conclude_proposal"
    description: str = "Conclude a core proposal"
    args_schema: Type[BaseModel] = CoreProposalContractsInput
    return_direct: bool = False

    def _deploy(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to conclude a proposal."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/core-proposals/conclude-proposal.ts",
            core_proposals_contract,
            proposal_contract,
        )

    def _run(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to conclude a proposal."""
        return self._deploy(core_proposals_contract, proposal_contract, **kwargs)

    async def _arun(
        self, core_proposals_contract: str, proposal_contract: str, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(core_proposals_contract, proposal_contract, **kwargs)


# Action Proposal Tools
class ActionGetLinkedVotingContractsTool(DaoBaseTool):
    name: str = "dao_action_get_linked_voting_contracts"
    description: str = "Get the linked voting contracts for action proposals"
    args_schema: Type[BaseModel] = ActionProposalInput
    return_direct: bool = False

    def _deploy(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get linked voting contracts."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/action-proposals/get-linked-voting-contracts.ts",
            action_proposals_contract,
        )

    def _run(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get linked voting contracts."""
        return self._deploy(action_proposals_contract, **kwargs)

    async def _arun(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(action_proposals_contract, **kwargs)


class ActionGetProposalTool(DaoBaseTool):
    name: str = "dao_action_get_proposal"
    description: str = "Get details of an action proposal"
    args_schema: Type[BaseModel] = ActionProposalInput
    return_direct: bool = False

    def _deploy(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to get proposal details."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/action-proposals/get-proposal.ts",
            action_proposals_contract,
            str(proposal_id),
        )

    def _run(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to get proposal details."""
        return self._deploy(action_proposals_contract, proposal_id, **kwargs)

    async def _arun(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(action_proposals_contract, proposal_id, **kwargs)


class ActionGetTotalVotesTool(DaoBaseTool):
    name: str = "dao_action_get_total_votes"
    description: str = "Get total votes for an action proposal"
    args_schema: Type[BaseModel] = ActionProposalInput
    return_direct: bool = False

    def _deploy(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to get total votes."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/action-proposals/get-total-votes.ts",
            action_proposals_contract,
            str(proposal_id),
        )

    def _run(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to get total votes."""
        return self._deploy(action_proposals_contract, proposal_id, **kwargs)

    async def _arun(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(action_proposals_contract, proposal_id, **kwargs)


class ActionGetVotingPowerTool(DaoBaseTool):
    name: str = "dao_action_get_voting_power"
    description: str = "Get voting power for action proposals"
    args_schema: Type[BaseModel] = ActionProposalInput
    return_direct: bool = False

    def _deploy(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get voting power."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/action-proposals/get-voting-power.ts",
            action_proposals_contract,
        )

    def _run(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get voting power."""
        return self._deploy(action_proposals_contract, **kwargs)

    async def _arun(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(action_proposals_contract, **kwargs)


class ActionVoteOnProposalTool(DaoBaseTool):
    name: str = "dao_action_vote_on_proposal"
    description: str = "Vote on an action proposal"
    args_schema: Type[BaseModel] = ActionVoteInput
    return_direct: bool = False

    def _deploy(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        amount: str,
        for_vote: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to vote on a proposal."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/action-proposals/vote-on-proposal.ts",
            action_proposals_contract,
            str(proposal_id),
            amount,
            str(for_vote).lower(),
        )

    def _run(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        amount: str,
        for_vote: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to vote on a proposal."""
        return self._deploy(
            action_proposals_contract, proposal_id, amount, for_vote, **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        amount: str,
        for_vote: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract, proposal_id, amount, for_vote, **kwargs
        )


class ActionConcludeProposalTool(DaoBaseTool):
    name: str = "dao_action_conclude_proposal"
    description: str = "Conclude an action proposal"
    args_schema: Type[BaseModel] = ActionProposalInput
    return_direct: bool = False

    def _deploy(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to conclude a proposal."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/action-proposals/conclude-proposal.ts",
            action_proposals_contract,
            str(proposal_id),
        )

    def _run(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to conclude a proposal."""
        return self._deploy(action_proposals_contract, proposal_id, **kwargs)

    async def _arun(
        self, action_proposals_contract: str, proposal_id: int, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(action_proposals_contract, proposal_id, **kwargs)


class ActionGetTotalProposalsTool(DaoBaseTool):
    name: str = "dao_action_get_total_proposals"
    description: str = "Get total number of action proposals"
    args_schema: Type[BaseModel] = ActionProposalInput
    return_direct: bool = False

    def _deploy(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get total proposals."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/action-proposals/get-total-proposals.ts",
            action_proposals_contract,
        )

    def _run(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get total proposals."""
        return self._deploy(action_proposals_contract, **kwargs)

    async def _arun(self, action_proposals_contract: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(action_proposals_contract, **kwargs)


class BuyTokenTool(DaoBaseTool):
    name: str = "dao_buy_token"
    description: str = "Buy tokens from the bonding curve DEX"
    args_schema: Type[BaseModel] = BuyTokenInput
    return_direct: bool = False

    def _deploy(
        self, dex_contract: str, token_contract: str, stx_amount: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to buy tokens."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtcdev-dao",
            "extensions/buy-token.ts",
            dex_contract,
            token_contract,
            stx_amount,
        )

    def _run(
        self, dex_contract: str, token_contract: str, stx_amount: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to buy tokens."""
        return self._deploy(dex_contract, token_contract, stx_amount, **kwargs)

    async def _arun(
        self, dex_contract: str, token_contract: str, stx_amount: str, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(dex_contract, token_contract, stx_amount, **kwargs)
