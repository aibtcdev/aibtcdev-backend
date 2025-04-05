from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class GenerateCoreProposalInput(BaseModel):
    """Input schema for generating a core proposal."""

    dao_deployer_address: str = Field(
        ...,
        description="The address of the DAO deployer",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
    )
    dao_token_symbol: str = Field(
        ...,
        description="The token symbol for the DAO",
        example="aibtc",
    )
    proposal_contract_name: str = Field(
        ...,
        description="The name of the proposal contract",
        example="aibtc-treasury-withdraw-stx",
    )
    proposal_args: Dict[str, str] = Field(
        ...,
        description="Arguments for the proposal in key-value format",
        example={
            "stx_amount": "1000000",
            "recipient_address": "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
        },
    )
    generate_files: bool = Field(
        False,
        description="Whether to generate and save proposal files",
    )


class GenerateCoreProposalTool(BaseTool):
    name: str = "dao_generate_core_proposal"
    description: str = (
        "Generate a core proposal for the DAO. "
        "This will create the proposal contract but not deploy it. "
        "Returns the generated proposal details if successful."
    )
    args_schema: Type[BaseModel] = GenerateCoreProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_deployer_address: str,
        dao_token_symbol: str,
        proposal_contract_name: str,
        proposal_args: Dict[str, str],
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to generate a core proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            dao_deployer_address,
            dao_token_symbol,
            proposal_contract_name,
            str(proposal_args).replace("'", '"'),  # Convert Python dict to JSON string
            str(generate_files).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/core-proposals",
            "generate-core-proposal.ts",
            *args,
        )

    def _run(
        self,
        dao_deployer_address: str,
        dao_token_symbol: str,
        proposal_contract_name: str,
        proposal_args: Dict[str, str],
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to generate a core proposal."""
        return self._deploy(
            dao_deployer_address,
            dao_token_symbol,
            proposal_contract_name,
            proposal_args,
            generate_files,
            **kwargs,
        )

    async def _arun(
        self,
        dao_deployer_address: str,
        dao_token_symbol: str,
        proposal_contract_name: str,
        proposal_args: Dict[str, str],
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            dao_deployer_address,
            dao_token_symbol,
            proposal_contract_name,
            proposal_args,
            generate_files,
            **kwargs,
        )


class DeployCoreProposalInput(BaseModel):
    """Input schema for deploying a core proposal."""

    dao_deployer_address: str = Field(
        ...,
        description="The address of the DAO deployer",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
    )
    dao_token_symbol: str = Field(
        ...,
        description="The token symbol for the DAO",
        example="aibtc",
    )
    proposal_contract_name: str = Field(
        ...,
        description="The name of the proposal contract",
        example="aibtc-treasury-withdraw-stx",
    )
    proposal_args: Dict[str, str] = Field(
        ...,
        description="Arguments for the proposal in key-value format",
        example={
            "stx_amount": "1000000",
            "recipient_address": "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
        },
    )
    generate_files: bool = Field(
        False,
        description="Whether to generate and save proposal files",
    )


class DeployCoreProposalTool(BaseTool):
    name: str = "dao_deploy_core_proposal"
    description: str = (
        "Deploy a core proposal for the DAO. "
        "This will generate and deploy the proposal contract. "
        "This is a required step before proposing. "
        "Returns the deployment details if successful."
    )
    args_schema: Type[BaseModel] = DeployCoreProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_deployer_address: str,
        dao_token_symbol: str,
        proposal_contract_name: str,
        proposal_args: Dict[str, str],
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy a core proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            dao_deployer_address,
            dao_token_symbol,
            proposal_contract_name,
            str(proposal_args).replace("'", '"'),  # Convert Python dict to JSON string
            str(generate_files).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/core-proposals",
            "deploy-core-proposal.ts",
            *args,
        )

    def _run(
        self,
        dao_deployer_address: str,
        dao_token_symbol: str,
        proposal_contract_name: str,
        proposal_args: Dict[str, str],
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy a core proposal."""
        return self._deploy(
            dao_deployer_address,
            dao_token_symbol,
            proposal_contract_name,
            proposal_args,
            generate_files,
            **kwargs,
        )

    async def _arun(
        self,
        dao_deployer_address: str,
        dao_token_symbol: str,
        proposal_contract_name: str,
        proposal_args: Dict[str, str],
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            dao_deployer_address,
            dao_token_symbol,
            proposal_contract_name,
            proposal_args,
            generate_files,
            **kwargs,
        )
