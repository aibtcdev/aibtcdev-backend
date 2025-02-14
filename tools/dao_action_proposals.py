from uuid import UUID
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from tools.bun import BunScriptRunner
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            action_proposal_contract,
            resource_name,
            resource_description,
            str(resource_price),
        ]
        
        if resource_url:
            args.append(resource_url)

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-add-resource.ts",
            *args
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            action_proposal_contract,
            token_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-allow-asset.ts",
            *args
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            action_proposal_contract,
            message,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-send-message.ts",
            *args
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            action_proposal_contract,
            account_holder,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-set-account-holder.ts",
            *args
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            action_proposal_contract,
            str(withdrawal_amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-set-withdrawal-amount.ts",
            *args
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            action_proposals_contract,
            action_proposal_contract,
            str(withdrawal_period),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "action-proposals",
            "propose-action-set-withdrawal-period.ts",
            *args
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

