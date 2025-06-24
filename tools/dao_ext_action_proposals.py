from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class DaoBaseInput(BaseModel):
    """Base input schema for dao tools that do not require parameters."""

    pass


class ProposeActionSendMessageInput(BaseModel):
    """Input schema for proposing to send a message action."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes sending a message through the DAO.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-send-message"
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=["ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token"],
    )
    message: str = Field(
        ...,
        description="Message to be sent through the DAO proposal system, verified to be from the DAO and posted to Twitter/X automatically if successful.",
        examples=["This is my message."],
    )
    memo: Optional[str] = Field(
        None,
        description="Optional memo to include with the proposal",
        examples=["This is my memo."],
    )


class ProposeActionSendMessageTool(BaseTool):
    name: str = "dao_propose_action_send_message"
    description: str = (
        "This creates a proposal that DAO members can vote on to send a specific message that gets "
        "stored on-chain and automatically posted to the DAO Twitter/X account."
    )
    args_schema: Type[BaseModel] = ProposeActionSendMessageInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        message: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose sending a message."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            message,
        ]

        if memo:
            args.append(memo)

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/public",
            "create-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        message: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose sending a message."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            message,
            memo,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        message: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            message,
            memo,
            **kwargs,
        )


class VoteOnActionProposalInput(BaseModel):
    """Input schema for voting on an action proposal."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(
        ..., description="ID of the proposal to vote on", example=13
    )
    vote_for: bool = Field(
        ..., description="True for yes/for, False for no/against", example=True
    )


class VoteOnActionProposalTool(BaseTool):
    name: str = "dao_action_vote_on_proposal"
    description: str = (
        "Vote on an existing action proposal in the DAO. "
        "Allows casting a vote (true/false) on a specific proposal ID "
        "in the provided action proposals contract."
    )
    args_schema: Type[BaseModel] = VoteOnActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        vote_for: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            dao_action_proposal_voting_contract,
            str(proposal_id),
            str(vote_for).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/public",
            "vote-on-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        vote_for: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal."""
        return self._deploy(
            dao_action_proposal_voting_contract, proposal_id, vote_for, **kwargs
        )

    async def _arun(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        vote_for: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            dao_action_proposal_voting_contract, proposal_id, vote_for, **kwargs
        )


class ConcludeActionProposalInput(BaseModel):
    """Input schema for concluding an action proposal."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(
        ..., description="ID of the proposal to conclude", example=13
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the original action proposal submitted for execution as part of the proposal",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-send-message"
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=["ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token"],
    )


class ConcludeActionProposalTool(BaseTool):
    name: str = "dao_action_conclude_proposal"
    description: str = (
        "Conclude an existing action proposal in the DAO. "
        "This finalizes the proposal and executes the action if the vote passed."
    )
    args_schema: Type[BaseModel] = ConcludeActionProposalInput
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
        action_proposals_voting_extension: str,
        dao_token_contract_address: str,
        proposal_id: int,
        action_proposal_contract_to_execute: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude an action proposal."""
        if self.seed_phrase is None and self.wallet_id is None:
            return {
                "success": False,
                "message": "Either seed phrase or wallet ID is required",
                "data": None,
            }

        args = [
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            str(proposal_id),
        ]

        # Use seed phrase if available, otherwise fall back to wallet_id
        if self.seed_phrase:
            return BunScriptRunner.bun_run_with_seed_phrase(
                self.seed_phrase,
                "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/public",
                "conclude-action-proposal.ts",
                *args,
            )
        else:
            return BunScriptRunner.bun_run(
                self.wallet_id,
                "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/public",
                "conclude-action-proposal.ts",
                *args,
            )

    def _run(
        self,
        action_proposals_voting_extension: str,
        dao_token_contract_address: str,
        proposal_id: int,
        action_proposal_contract_to_execute: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude an action proposal."""
        return self._deploy(
            action_proposals_voting_extension,
            dao_token_contract_address,
            proposal_id,
            action_proposal_contract_to_execute,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        dao_token_contract_address: str,
        proposal_id: int,
        action_proposal_contract_to_execute: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            dao_token_contract_address,
            proposal_id,
            action_proposal_contract_to_execute,
            **kwargs,
        )


class GetLiquidSupplyInput(BaseModel):
    """Input schema for getting the liquid supply."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    stacks_block_height: int = Field(
        ..., description="Stacks block height to query the liquid supply at"
    )


class GetLiquidSupplyTool(BaseTool):
    name: str = "dao_action_get_liquid_supply"
    description: str = (
        "Get the liquid supply of the DAO token at a specific Stacks block height. "
        "Returns the total amount of tokens that are liquid at that block."
    )
    args_schema: Type[BaseModel] = GetLiquidSupplyInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_voting_extension: str,
        stacks_block_height: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get the liquid supply."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            str(stacks_block_height),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/read-only",
            "get-liquid-supply.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        stacks_block_height: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get the liquid supply."""
        return self._deploy(
            action_proposals_voting_extension, stacks_block_height, **kwargs
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        stacks_block_height: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension, stacks_block_height, **kwargs
        )


class GetProposalInput(BaseModel):
    """Input schema for getting proposal data."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to retrieve")


class GetProposalTool(BaseTool):
    name: str = "dao_action_get_proposal"
    description: str = (
        "Get the data for a specific proposal from the DAO action proposals contract. "
        "Returns all stored information about the proposal if it exists."
    )
    args_schema: Type[BaseModel] = GetProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_voting_extension: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get proposal data."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            str(proposal_id),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/read-only",
            "get-proposal.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get proposal data."""
        return self._deploy(action_proposals_voting_extension, proposal_id, **kwargs)

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(action_proposals_voting_extension, proposal_id, **kwargs)


class GetVotingConfigurationInput(BaseModel):
    """Input schema for getting voting configuration."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )


class GetVotingConfigurationTool(BaseTool):
    name: str = "dao_action_get_voting_configuration"
    description: str = (
        "Get the voting configuration from the DAO action proposals contract. "
        "Returns the current voting parameters and settings used for proposals."
    )
    args_schema: Type[BaseModel] = GetVotingConfigurationInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_voting_extension: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get voting configuration."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/read-only",
            "get-voting-configuration.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get voting configuration."""
        return self._deploy(action_proposals_voting_extension, **kwargs)

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(action_proposals_voting_extension, **kwargs)


class GetVotingPowerInput(BaseModel):
    """Input schema for getting voting power."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to check")
    voter_address: str = Field(
        ...,
        description="Address of the voter to check voting power for",
        examples=["ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18"],
    )


class GetVotingPowerTool(BaseTool):
    name: str = "dao_action_get_voting_power"
    description: str = (
        "Get the voting power of a specific address for a proposal. "
        "Returns the number of votes the address can cast on the given proposal."
    )
    args_schema: Type[BaseModel] = GetVotingPowerInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_voting_extension: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get voting power."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            str(proposal_id),
            voter_address,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/read-only",
            "get-voting-power.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get voting power."""
        return self._deploy(
            action_proposals_voting_extension, proposal_id, voter_address, **kwargs
        )


class VetoActionProposalInput(BaseModel):
    """Input schema for vetoing an action proposal."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to veto", example=1)


class VetoActionProposalTool(BaseTool):
    name: str = "dao_action_veto_proposal"
    description: str = (
        "Veto an existing action proposal in the DAO. "
        "Allows casting a veto vote on a specific proposal ID "
        "in the provided action proposals contract."
    )
    args_schema: Type[BaseModel] = VetoActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to veto an action proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            dao_action_proposal_voting_contract,
            str(proposal_id),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/public",
            "veto-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to veto an action proposal."""
        return self._deploy(dao_action_proposal_voting_contract, proposal_id, **kwargs)

    async def _arun(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(dao_action_proposal_voting_contract, proposal_id, **kwargs)


class GetTotalProposalsInput(BaseModel):
    """Input schema for getting total proposals data."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )


class GetTotalProposalsTool(BaseTool):
    name: str = "dao_action_get_total_proposals"
    description: str = (
        "Get the total proposals data from the DAO action proposals contract. "
        "Returns counts of proposals and last proposal block information."
    )
    args_schema: Type[BaseModel] = GetTotalProposalsInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_action_proposal_voting_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get total proposals data."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            dao_action_proposal_voting_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/read-only",
            "get-total-proposals.ts",
            *args,
        )

    def _run(
        self,
        dao_action_proposal_voting_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get total proposals data."""
        return self._deploy(dao_action_proposal_voting_contract, **kwargs)

    async def _arun(
        self,
        dao_action_proposal_voting_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(dao_action_proposal_voting_contract, **kwargs)


class GetVetoVoteRecordInput(BaseModel):
    """Input schema for getting a veto vote record."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to check")
    voter_address: str = Field(
        ...,
        description="Address of the voter to check the veto vote record for",
        examples=["ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18"],
    )


class GetVetoVoteRecordTool(BaseTool):
    name: str = "dao_action_get_veto_vote_record"
    description: str = (
        "Get the veto vote record for a specific voter on a proposal. "
        "Returns the amount of veto votes if a record exists, otherwise null."
    )
    args_schema: Type[BaseModel] = GetVetoVoteRecordInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get a veto vote record."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            dao_action_proposal_voting_contract,
            str(proposal_id),
            voter_address,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/read-only",
            "get-veto-vote-record.ts",
            *args,
        )

    def _run(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get a veto vote record."""
        return self._deploy(
            dao_action_proposal_voting_contract,
            proposal_id,
            voter_address,
            **kwargs,
        )

    async def _arun(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            dao_action_proposal_voting_contract,
            proposal_id,
            voter_address,
            **kwargs,
        )


class GetVoteRecordInput(BaseModel):
    """Input schema for getting a vote record."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to check")
    voter_address: str = Field(
        ...,
        description="Address of the voter to check the vote record for",
        examples=["ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18"],
    )


class GetVoteRecordTool(BaseTool):
    name: str = "dao_action_get_vote_record"
    description: str = (
        "Get the vote record for a specific voter on a proposal. "
        "Returns the vote (true/false) and amount if a record exists, otherwise null."
    )
    args_schema: Type[BaseModel] = GetVoteRecordInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get a vote record."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            dao_action_proposal_voting_contract,
            str(proposal_id),
            voter_address,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/read-only",
            "get-vote-record.ts",
            *args,
        )

    def _run(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get a vote record."""
        return self._deploy(
            dao_action_proposal_voting_contract,
            proposal_id,
            voter_address,
            **kwargs,
        )

    async def _arun(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            dao_action_proposal_voting_contract,
            proposal_id,
            voter_address,
            **kwargs,
        )


class GetVoteRecordsInput(BaseModel):
    """Input schema for getting vote records (vote and veto vote)."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting"
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to check")
    voter_address: str = Field(
        ...,
        description="Address of the voter to check vote records for",
        examples=["ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18"],
    )


class GetVoteRecordsTool(BaseTool):
    name: str = "dao_action_get_vote_records"
    description: str = (
        "Get both the regular vote record and veto vote record for a specific voter on a proposal. "
        "Returns an object containing 'voteRecord' (vote and amount, or null) and "
        "'vetoVoteRecord' (amount, or null)."
    )
    args_schema: Type[BaseModel] = GetVoteRecordsInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get vote records."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            dao_action_proposal_voting_contract,
            str(proposal_id),
            voter_address,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/dao-tools/extensions/action-proposal-voting/read-only",
            "get-vote-records.ts",
            *args,
        )

    def _run(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get vote records."""
        return self._deploy(
            dao_action_proposal_voting_contract,
            proposal_id,
            voter_address,
            **kwargs,
        )

    async def _arun(
        self,
        dao_action_proposal_voting_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            dao_action_proposal_voting_contract,
            proposal_id,
            voter_address,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension, proposal_id, voter_address, **kwargs
        )
