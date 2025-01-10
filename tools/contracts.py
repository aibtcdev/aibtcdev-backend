from .bun import BunScriptRunner
from langchain.tools import BaseTool
from lib.hiro import HiroApi
from pydantic import BaseModel, Field
from services.daos import TokenServiceError, generate_token_dependencies
from typing import Any, Dict, Optional, Type, Union
from uuid import UUID


class ContractSIP10DeployInput(BaseModel):
    """Input schema for ContractSIP10Deploy tool."""

    token_symbol: str = Field(..., description="Symbol of the token.")
    token_name: str = Field(..., description="Name of the token.")
    token_description: str = Field(
        ..., description="Description of the token. Default is an empty string."
    )
    token_decimals: int = Field(
        ..., description="Number of decimals for the token. Default is 6"
    )
    token_max_supply: str = Field(
        ..., description="Initial supply of the token. Default is 1000000000"
    )


class ContractSIP10DeployTool(BaseTool):
    name: str = "contract_sip10_deploy"
    description: str = (
        "Deploy a new token contract following the SIP-10 standard. "
        "Example usage: 'deploy a token named 'Human' with a symbol 'HUMAN' and a description 'The Human Token'"
    )
    args_schema: Type[BaseModel] = ContractSIP10DeployInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        token_symbol: str,
        token_name: str,
        token_decimals: int,
        token_description: str,
        token_max_supply: str,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to deploy a SIP-10 token contract."""
        try:
            token_url, token_data = generate_token_dependencies(
                token_name,
                token_symbol,
                token_description,
                token_decimals,
                token_max_supply,
            )

            return BunScriptRunner.bun_run(
                self.wallet_id,
                "sip-010-ft",
                "deploy.ts",
                token_name,
                token_symbol,
                str(token_decimals),
                token_url,
                str(token_max_supply),
            )

        except TokenServiceError as e:
            error_msg = f"Failed to create token dependencies: {str(e)}"
            if e.details:
                error_msg += f"\nDetails: {e.details}"
            return {"success": False, "error": error_msg, "details": e.details}
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during token deployment: {str(e)}",
            }

    def _run(
        self,
        token_symbol: str,
        token_name: str,
        token_decimals: int,
        token_description: str,
        token_max_supply: str,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to deploy a SIP-10 token contract."""
        return self._deploy(
            token_symbol,
            token_name,
            token_decimals,
            token_description,
            token_max_supply,
        )

    async def _arun(
        self,
        token_symbol: str,
        token_name: str,
        token_decimals: int,
        token_description: str,
        token_max_supply: str,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(
            token_symbol,
            token_name,
            token_decimals,
            token_description,
            token_max_supply,
        )


class ContractSIP10InfoInput(BaseModel):
    """Input schema for ContractSIP10Info tool."""

    contract_address: str = Field(
        ...,
        description="Contract address of the token. Format: contract_address.contract_name",
    )


class ContractSIP10InfoTool(BaseTool):
    name: str = "contract_sip10_info"
    description: str = (
        "Get token information including name, symbol, decimals, and supply for a SIP-10 token. "
        "Example usage: 'get info about the token named 'SP295MNE41DC74QYCPRS8N37YYMC06N6Q3T5P1YC2.foundry-6s-FSwIm'"
    )
    args_schema: Type[BaseModel] = ContractSIP10InfoInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        contract_address: str,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get SIP-10 token information."""
        try:
            return BunScriptRunner.bun_run(
                self.wallet_id,
                "sip-010-ft",
                "get-token-info.ts",
                contract_address,
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during token info retrieval: {str(e)}",
            }

    def _run(
        self,
        contract_address: str,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get SIP-10 token information."""
        return self._deploy(contract_address)

    async def _arun(
        self,
        contract_address: str,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(contract_address)


class FetchContractSourceInput(BaseModel):
    """Input schema for FetchContractSource tool."""

    contract_address: str = Field(
        ...,
        description="The contract's address (e.g., SP000... or SP295MNE41DC74QYCPRS8N37YYMC06N6Q3T5P1YC2.foundry-6s-FSwIm)",
    )
    contract_name: str = Field(..., description="The name of the contract")


class FetchContractSourceTool(BaseTool):
    name: str = "contract_fetch_source"
    description: str = (
        "Fetch the source code of a contract using the Hiro API. "
        "Example usage: 'fetch the source code of the contract named 'SP295MNE41DC74QYCPRS8N37YYMC06N6Q3T5P1YC2.foundry-6s-FSwIm'"
    )
    args_schema: Type[BaseModel] = FetchContractSourceInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        contract_address: str,
        contract_name: str,
    ):
        """Execute the tool to fetch contract source code."""
        try:
            api = HiroApi()
            result = api.get_contract_source(contract_address, contract_name)

            if "source" in result:
                return result["source"]
            else:
                return f"Error: Could not find source code. API response: {result}"
        except Exception as e:
            return f"Error fetching contract source: {str(e)}"

    def _run(
        self,
        contract_address: str,
        contract_name: str,
        **kwargs,
    ) -> str:
        """Execute the tool to fetch contract source code."""
        return self._deploy(contract_address, contract_name)

    async def _arun(
        self,
        contract_address: str,
        contract_name: str,
        **kwargs,
    ) -> str:
        """Async version of the tool."""
        return self._deploy(contract_address, contract_name)
