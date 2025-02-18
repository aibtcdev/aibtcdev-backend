from uuid import UUID
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from tools.bun import BunScriptRunner
from tools.dao_base import DAOToolResponse
from typing import Dict, Optional, Type, Any

class DaoBaseInput(BaseModel):
    """Base input schema for dao tools that do not require parameters."""
    pass

class ProposeActionAddResourceInput(BaseModel):
    """Input schema for proposing to add a resource action."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    action_proposal_contract: str = Field(
        ..., 
        description="Contract ID of the action proposal"
    )
    resource_name: str = Field(
        ..., 
        description="Name of the resource to add"
    )
    resource_description: str = Field(
        ..., 
        description="Description of the resource"
    )
    resource_price: int = Field(
        ..., 
        description="Price of the resource in microstacks"
    )
    resource_url: Optional[str] = Field(
        None,
        description="Optional URL associated with the resource"
    )

class ProposeActionAddResourceTool(BaseTool):
    name: str = "dao_propose_action_add_resource"
    description: str = (
        "Propose an action to add a new resource to the DAO. "
        "This creates a proposal that DAO members can vote on to add a new resource "
        "with specified name, description, price, and optional URL."
    )
    args_schema: Type[BaseModel] = ProposeActionAddResourceInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        resource_name: str,
        resource_description: str,
        resource_price: int,
        resource_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose adding a resource."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [
            action_proposals_contract,
            action_proposal_contract,
            resource_name,
            resource_description,
            str(resource_price),
        ]
        
        if resource_url:
            args.append(resource_url)

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-add-resource.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("message", "Unknown error"),
                result.get("data")
            )
            
        return DAOToolResponse.success_response(
            result.get("message", "Successfully retrieved current DAO charter"),
            result.get("data")
        )

    def _run(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        resource_name: str,
        resource_description: str,
        resource_price: int,
        resource_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose adding a resource."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            resource_name,
            resource_description,
            resource_price,
            resource_url,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        resource_name: str,
        resource_description: str,
        resource_price: int,
        resource_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            resource_name,
            resource_description,
            resource_price,
            resource_url,
            **kwargs
        )

class ProposeActionAllowAssetInput(BaseModel):
    """Input schema for proposing to allow an asset action."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    action_proposal_contract: str = Field(
        ..., 
        description="Contract ID of the action proposal"
    )
    token_contract: str = Field(
        ..., 
        description="Contract ID of the token to allow"
    )

class ProposeActionAllowAssetTool(BaseTool):
    name: str = "dao_propose_action_allow_asset"
    description: str = (
        "Propose an action to allow a new asset/token in the DAO. "
        "This creates a proposal that DAO members can vote on to allow "
        "a specific token contract to be used within the DAO."
    )
    args_schema: Type[BaseModel] = ProposeActionAllowAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose allowing an asset."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [
            action_proposals_contract,
            action_proposal_contract,
            token_contract,
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-allow-asset.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("message", "Unknown error"),
                result.get("data")
            )
            
        return DAOToolResponse.success_response(
            result.get("message", "Successfully retrieved current charter version"),
            result.get("data")
        )

    def _run(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose allowing an asset."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            token_contract,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            token_contract,
            **kwargs
        )

class ProposeActionSendMessageInput(BaseModel):
    """Input schema for proposing to send a message action."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    action_proposal_contract: str = Field(
        ..., 
        description="Contract ID of the action proposal"
    )
    message: str = Field(
        ..., 
        description="Message to be sent"
    )

class ProposeActionSendMessageTool(BaseTool):
    name: str = "dao_propose_action_send_message"
    description: str = (
        "Propose an action to send a message through the DAO. "
        "This creates a proposal that DAO members can vote on to send "
        "a specific message."
    )
    args_schema: Type[BaseModel] = ProposeActionSendMessageInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose sending a message."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [
            action_proposals_contract,
            action_proposal_contract,
            message,
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-send-message.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("message", "Unknown error"),
                result.get("data")
            )
            
        return DAOToolResponse.success_response(
            result.get("message", "Successfully retrieved DAO charter version"),
            result.get("data")
        )

    def _run(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose sending a message."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            message,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            message,
            **kwargs
        )

class ProposeActionSetAccountHolderInput(BaseModel):
    """Input schema for proposing to set account holder action."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    action_proposal_contract: str = Field(
        ..., 
        description="Contract ID of the action proposal"
    )
    account_holder: str = Field(
        ..., 
        description="Address of the new account holder"
    )

class ProposeActionSetAccountHolderTool(BaseTool):
    name: str = "dao_propose_action_set_account_holder"
    description: str = (
        "Propose an action to set a new account holder for the DAO. "
        "This creates a proposal that DAO members can vote on to change "
        "the account holder to a specified address."
    )
    args_schema: Type[BaseModel] = ProposeActionSetAccountHolderInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new account holder."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [
            action_proposals_contract,
            action_proposal_contract,
            account_holder,
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-set-account-holder.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new account holder."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            account_holder,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            account_holder,
            **kwargs
        )

class ProposeActionSetWithdrawalAmountInput(BaseModel):
    """Input schema for proposing to set withdrawal amount action."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    action_proposal_contract: str = Field(
        ..., 
        description="Contract ID of the action proposal"
    )
    withdrawal_amount: int = Field(
        ..., 
        description="New withdrawal amount to set"
    )

class ProposeActionSetWithdrawalAmountTool(BaseTool):
    name: str = "dao_propose_action_set_withdrawal_amount"
    description: str = (
        "Propose an action to set a new withdrawal amount for the DAO's bank account. "
        "This creates a proposal that DAO members can vote on to change "
        "the withdrawal amount to a specified value."
    )
    args_schema: Type[BaseModel] = ProposeActionSetWithdrawalAmountInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new withdrawal amount."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [
            action_proposals_contract,
            action_proposal_contract,
            str(withdrawal_amount),
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-set-withdrawal-amount.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new withdrawal amount."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            withdrawal_amount,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            withdrawal_amount,
            **kwargs
        )

class ProposeActionSetWithdrawalPeriodInput(BaseModel):
    """Input schema for proposing to set withdrawal period action."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    action_proposal_contract: str = Field(
        ..., 
        description="Contract ID of the action proposal"
    )
    withdrawal_period: int = Field(
        ..., 
        description="New withdrawal period to set"
    )

class ProposeActionSetWithdrawalPeriodTool(BaseTool):
    name: str = "dao_propose_action_set_withdrawal_period"
    description: str = (
        "Propose an action to set a new withdrawal period for the DAO's bank account. "
        "This creates a proposal that DAO members can vote on to change "
        "the withdrawal period to a specified value."
    )
    args_schema: Type[BaseModel] = ProposeActionSetWithdrawalPeriodInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new withdrawal period."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [
            action_proposals_contract,
            action_proposal_contract,
            str(withdrawal_period),
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-set-withdrawal-period.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new withdrawal period."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            withdrawal_period,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            withdrawal_period,
            **kwargs
        )

class ProposeActionToggleResourceInput(BaseModel):
    """Input schema for proposing to toggle a resource action."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    action_proposal_contract: str = Field(
        ..., 
        description="Contract ID of the action proposal"
    )
    resource_name: str = Field(
        ..., 
        description="Name of the resource to toggle"
    )


class VoteOnActionProposalInput(BaseModel):
    """Input schema for voting on an action proposal."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to vote on"
    )
    vote: bool = Field(
        ...,
        description="True for yes/for, False for no/against"
    )

class VoteOnActionProposalTool(BaseTool):
    name: str = "dao_action_vote_on_proposal"
    description: str = (
        "Vote on an existing action proposal in the DAO. "
        "Allows casting a vote (true/false) on a specific proposal ID "
        "in the action proposals contract."
    )
    args_schema: Type[BaseModel] = VoteOnActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            str(proposal_id),
            str(vote).lower(),
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "vote-on-proposal.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            vote,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            vote,
            **kwargs
        )

class ConcludeActionProposalInput(BaseModel):
    """Input schema for concluding an action proposal."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to conclude"
    )
    action_proposal_contract: str = Field(
        ...,
        description="Contract ID of the action proposal"
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

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        action_proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude an action proposal."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            str(proposal_id),
            action_proposal_contract,
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "conclude-proposal.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        action_proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude an action proposal."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            action_proposal_contract,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        action_proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            action_proposal_contract,
            **kwargs
        )

class GetLiquidSupplyInput(BaseModel):
    """Input schema for getting the liquid supply."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    stacks_block_height: int = Field(
        ...,
        description="Stacks block height to query the liquid supply at"
    )

class GetLiquidSupplyTool(BaseTool):
    name: str = "dao_action_get_liquid_supply"
    description: str = (
        "Get the liquid supply of the DAO token at a specific Stacks block height. "
        "Returns the total amount of tokens that are liquid/transferable at that block."
    )
    args_schema: Type[BaseModel] = GetLiquidSupplyInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        stacks_block_height: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get the liquid supply."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            str(stacks_block_height),
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "get-liquid-supply.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        stacks_block_height: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get the liquid supply."""
        return self._deploy(
            action_proposals_contract,
            stacks_block_height,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        stacks_block_height: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            stacks_block_height,
            **kwargs
        )

class GetProposalInput(BaseModel):
    """Input schema for getting proposal data."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to retrieve"
    )

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
        action_proposals_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get proposal data."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            str(proposal_id),
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "get-proposal.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get proposal data."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            **kwargs
        )

class GetTotalVotesInput(BaseModel):
    """Input schema for getting total votes for a voter."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to check"
    )
    voter_address: str = Field(
        ...,
        description="Address of the voter to check"
    )

class GetTotalVotesTool(BaseTool):
    name: str = "dao_action_get_total_votes"
    description: str = (
        "Get the total votes cast by a specific voter on a proposal. "
        "Returns the number of votes the voter has cast on the given proposal."
    )
    args_schema: Type[BaseModel] = GetTotalVotesInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get total votes."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            str(proposal_id),
            voter_address,
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "get-total-votes.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get total votes."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            voter_address,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            voter_address,
            **kwargs
        )

class GetVotingConfigurationInput(BaseModel):
    """Input schema for getting voting configuration."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
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
        action_proposals_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get voting configuration."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "get-voting-configuration.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get voting configuration."""
        return self._deploy(
            action_proposals_contract,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            **kwargs
        )

class GetVotingPowerInput(BaseModel):
    """Input schema for getting voting power."""
    action_proposals_contract: str = Field(
        ..., 
        description="Contract ID of the DAO action proposals"
    )
    proposal_id: int = Field(
        ...,
        description="ID of the proposal to check"
    )
    voter_address: str = Field(
        ...,
        description="Address of the voter to check voting power for"
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
        action_proposals_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get voting power."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            str(proposal_id),
            voter_address,
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "get-voting-power.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
        )

    def _run(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get voting power."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            voter_address,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            proposal_id,
            voter_address,
            **kwargs
        )

class ProposeActionToggleResourceTool(BaseTool):
    name: str = "dao_propose_action_toggle_resource"
    description: str = (
        "Propose an action to toggle a resource's status in the payments and invoices contract. "
        "This creates a proposal that DAO members can vote on to enable or disable "
        "whether a specific resource can be paid for."
    )
    args_schema: Type[BaseModel] = ProposeActionToggleResourceInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose toggling a resource."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [
            action_proposals_contract,
            action_proposal_contract,
            resource_name,
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-toggle-resource-by-name.ts",
            *args
        )

    def _run(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose toggling a resource."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            resource_name,
            **kwargs
        )

    async def _arun(
        self,
        action_proposals_contract: str,
        action_proposal_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_contract,
            action_proposal_contract,
            resource_name,
            **kwargs
        )

