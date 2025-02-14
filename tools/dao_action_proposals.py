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

