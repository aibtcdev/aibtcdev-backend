from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class DaoBaseInput(BaseModel):
    """Base input schema for dao tools that do not require parameters."""

    pass


class ProposeActionAddResourceInput(BaseModel):
    """Input schema for proposing to add a resource action."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2"
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2"
        ],
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes adding a resource to the DAO.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-add-resource"
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-add-resource"
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    resource_name: str = Field(..., description="Name of the resource to add")
    resource_description: str = Field(..., description="Description of the resource")
    resource_price: int = Field(..., description="Price of the resource in microstacks")
    resource_url: Optional[str] = Field(
        None,
        description="Optional URL associated with the resource",
        examples=["https://www.example.com/resource"],
    )


class ProposeActionAddResourceTool(BaseTool):
    name: str = "dao_propose_action_add_resource"
    description: str = (
        "This creates a proposal that DAO members can vote on to add the new resource to the "
        " DAO resource contract with specified name, description, price, and optional URL."
    )
    args_schema: Type[BaseModel] = ProposeActionAddResourceInput
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
        resource_name: str,
        resource_description: str,
        resource_price: int,
        resource_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose adding a resource."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            resource_name,
            resource_description,
            str(resource_price),
        ]

        if resource_url:
            args.append(resource_url)

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "propose-action-add-resource.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        resource_name: str,
        resource_description: str,
        resource_price: int,
        resource_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose adding a resource."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            resource_name,
            resource_description,
            resource_price,
            resource_url,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        resource_name: str,
        resource_description: str,
        resource_price: int,
        resource_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            resource_name,
            resource_description,
            resource_price,
            resource_url,
            **kwargs,
        )


class ProposeActionAllowAssetInput(BaseModel):
    """Input schema for proposing to allow an asset action."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes allowing an asset in the DAO treasury.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-allow-asset",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    dao_token_contract_address_to_allow: str = Field(
        ...,
        description="Contract principal of the token to allow",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )


class ProposeActionAllowAssetTool(BaseTool):
    name: str = "dao_propose_action_allow_asset"
    description: str = (
        "This creates a proposal that DAO members can vote on to allow a specific "
        " token contract to be used within the DAO treasury contract."
    )
    args_schema: Type[BaseModel] = ProposeActionAllowAssetInput
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
        dao_token_contract_address_to_allow: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose allowing an asset."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            dao_token_contract_address_to_allow
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "propose-action-allow-asset.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        dao_token_contract_address_to_allow: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose allowing an asset."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            dao_token_contract_address_to_allow,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        dao_token_contract_address_to_allow: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            dao_token_contract_address_to_allow,
            **kwargs,
        )


class ProposeActionSendMessageInput(BaseModel):
    """Input schema for proposing to send a message action."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes sending a message through the DAO.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-send-message",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-send-message",
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    message: str = Field(
        ...,
        description="Message to be sent through the DAO proposal system, verified to be from the DAO and posted to Twitter/X automatically if successful.",
        examples=["gm gm from the $FACES DAO!"],
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

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "propose-action-send-message.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose sending a message."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            message,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            message,
            **kwargs,
        )


class ProposeActionSetAccountHolderInput(BaseModel):
    """Input schema for proposing to set account holder action."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes setting the account holder in a DAO timed vault.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-set-account-holder",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-set-account-holder",
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    account_holder: str = Field(
        ...,
        description="Address of the new account holder",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18",
            "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
            "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.contract",
        ],
    )


class ProposeActionSetAccountHolderTool(BaseTool):
    name: str = "dao_propose_action_set_account_holder"
    description: str = (
        "This creates a proposal that DAO members can vote on to change the account holder "
        "in a DAO timed vault to a specified standard or contract address."
    )
    args_schema: Type[BaseModel] = ProposeActionSetAccountHolderInput
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
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new account holder."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            account_holder,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "propose-action-set-account-holder.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new account holder."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            account_holder,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            account_holder,
            **kwargs,
        )


class ProposeActionSetWithdrawalAmountInput(BaseModel):
    """Input schema for proposing to set withdrawal amount action."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes setting the withdrawal amount in a DAO timed vault.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-set-withdrawal-amount",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-set-withdrawal-amount",
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    withdrawal_amount: int = Field(
        ...,
        description="New withdrawal amount to set in microSTX",
        examples=["50000000"],  # 50 STX
    )


class ProposeActionSetWithdrawalAmountTool(BaseTool):
    name: str = "dao_propose_action_set_withdrawal_amount"
    description: str = (
        "This creates a proposal that DAO members can vote on to change the withdrawal amount "
        " to a specified number of microSTX in a DAO timed vault."
    )
    args_schema: Type[BaseModel] = ProposeActionSetWithdrawalAmountInput
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
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new withdrawal amount."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            str(withdrawal_amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "propose-action-set-withdrawal-amount.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new withdrawal amount."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            withdrawal_amount,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            withdrawal_amount,
            **kwargs,
        )


class ProposeActionSetWithdrawalPeriodInput(BaseModel):
    """Input schema for proposing to set withdrawal period action."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes setting the withdrawal period in a DAO timed vault.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-set-withdrawal-period",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-set-withdrawal-period",
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    withdrawal_period: int = Field(
        ...,
        description="New withdrawal period to set in Bitcoin blocks",
        examples=["144"],  # 1 day in BTC blocks
    )


class ProposeActionSetWithdrawalPeriodTool(BaseTool):
    name: str = "dao_propose_action_set_withdrawal_period"
    description: str = (
        "This creates a proposal that DAO members can vote on to change the withdrawal period "
        " to a specified number of Bitcoin blocks in a DAO timed vault."
    )
    args_schema: Type[BaseModel] = ProposeActionSetWithdrawalPeriodInput
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
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new withdrawal period."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            str(withdrawal_period),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "propose-action-set-withdrawal-period.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose setting a new withdrawal period."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            withdrawal_period,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            withdrawal_period,
            **kwargs,
        )

class VoteOnActionProposalInput(BaseModel):
    """Input schema for voting on an action proposal."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to vote on")
    vote: bool = Field(..., description="True for yes/for, False for no/against")


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
        action_proposals_voting_extension: str,
        dao_token_contract_address: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            dao_token_contract_address,
            str(proposal_id),
            str(vote).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "vote-on-proposal.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        dao_token_contract_address: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal."""
        return self._deploy(
            action_proposals_voting_extension, dao_token_contract_address, proposal_id, vote, **kwargs
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        dao_token_contract_address: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension, dao_token_contract_address, proposal_id, vote, **kwargs
        )


class ConcludeActionProposalInput(BaseModel):
    """Input schema for concluding an action proposal."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to conclude")
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the original action proposal submitted for execution as part of the proposal",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-send-message",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-set-account-holder",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-toggle-resource",
        ],
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
        action_proposals_voting_extension: str,
        dao_token_contract_address: str,
        proposal_id: int,
        action_proposal_contract_to_execute: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude an action proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            dao_token_contract_address,
            str(proposal_id),
            action_proposal_contract_to_execute,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "conclude-proposal.ts",
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
    

class ProposeActionToggleResourceInput(BaseModel):
    """Input schema for proposing to toggle a resource action."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes toggling a resource in the DAO.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-toggle-resource",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-toggle-resource",
        ],
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-faktory",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-faktory",
        ],
    )
    resource_name: str = Field(
        ...,
        description="Name of the resource to toggle",
        examples=["apiv1", "protected-content", "1hr consulting"],
    )

class ProposeActionToggleResourceTool(BaseTool):
    name: str = "dao_propose_action_toggle_resource"
    description: str = (
        "This creates a proposal that DAO members can vote on to enable or disable "
        "whether a specific resource can be paid for in the DAO resource contract."
    )
    args_schema: Type[BaseModel] = ProposeActionToggleResourceInput
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
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose toggling a resource."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            resource_name,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/public",
            "propose-action-toggle-resource-by-name.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose toggling a resource."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            resource_name,
            **kwargs,
        )

    async def _arun(
        self,
        action_proposals_voting_extension: str,
        action_proposal_contract_to_execute: str,
        dao_token_contract_address: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            action_proposals_voting_extension,
            action_proposal_contract_to_execute,
            dao_token_contract_address,
            resource_name,
            **kwargs,
        )



class GetLiquidSupplyInput(BaseModel):
    """Input schema for getting the liquid supply."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
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
            "aibtc-dao/extensions/action-proposals/read-only",
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
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
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
            "aibtc-dao/extensions/action-proposals/read-only",
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


class GetTotalVotesInput(BaseModel):
    """Input schema for getting total votes for a voter."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
        ],
    )
    proposal_id: int = Field(..., description="ID of the proposal to check")
    voter_address: str = Field(..., description="Address of the voter to check")


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
        action_proposals_voting_extension: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get total votes."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            action_proposals_voting_extension,
            str(proposal_id),
            voter_address,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/action-proposals/read-only",
            "get-total-votes.ts",
            *args,
        )

    def _run(
        self,
        action_proposals_voting_extension: str,
        proposal_id: int,
        voter_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get total votes."""
        return self._deploy(
            action_proposals_voting_extension, proposal_id, voter_address, **kwargs
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


class GetVotingConfigurationInput(BaseModel):
    """Input schema for getting voting configuration."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
        examples=[
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
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
            "aibtc-dao/extensions/action-proposals/read-only",
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
        dao_token_contract_address: str,
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
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-action-proposals-v2",
            "ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.t3st-action-proposals-v2",
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
            "aibtc-dao/extensions/action-proposals/read-only",
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

