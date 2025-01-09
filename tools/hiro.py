from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Type


class STXPriceInput(BaseModel):
    """Input for STXPriceTool."""

    pass


class STXPriceTool(BaseTool):
    """Tool for getting the current STX price."""

    name: str = "stacks_stx_price"
    description: str = "A tool that can be used to get the current STX price"
    args_schema: Type[BaseModel] = STXPriceInput
    return_direct: bool = False

    def _deploy(self, *args, **kwargs) -> float:
        """Get the current STX price.

        Returns:
            float: The current STX price
        """
        from lib.hiro import HiroApi

        api = HiroApi()
        return str(api.get_stx_price())

    def _run(self, *args, **kwargs) -> str:
        """Get the current STX price."""
        return self._deploy(*args, **kwargs)

    async def _arun(self, *args, **kwargs) -> str:
        """Async implementation of getting STX price."""
        return self._deploy(*args, **kwargs)


class STXGetPrincipalAddressBalanceInput(BaseModel):
    """Input for STXGetPrincipalAddressBalance."""

    address: str = Field(
        ...,
        description="The principal address to get the balance for example: SP295MNE41DC74QYCPRS8N37YYMC06N6Q3T5P1YC2.foundry-6s-FSwIm or SP295MNE41DC74QYCPRS8N37YYMC06N6Q3T5P1YC2",
    )


class STXGetPrincipalAddressBalanceTool(BaseTool):
    """Tool for getting the STX balance of a principal address."""

    name: str = "stacks_get_principal_address_balance"
    description: str = (
        "A tool that can be used to get the STX balance of a principal address"
    )
    args_schema: Type[BaseModel] = STXGetPrincipalAddressBalanceInput
    return_direct: bool = False

    def _deploy(self, address: str) -> str:
        """Get the STX balance for a principal address.

        Args:
            address: The principal address to get the balance for

        Returns:
            str: The STX balance of the address
        """
        from lib.hiro import HiroApi

        api = HiroApi()
        return str(api.get_address_balance(address))

    def _run(self, address: str) -> str:
        """Get the STX balance for a principal address."""
        return self._deploy(address=address)

    async def _arun(self, address: str) -> str:
        """Async implementation of getting STX balance."""
        return self._deploy(address=address)


class STXGetContractInfoInput(BaseModel):
    """Input for STXGetContractInfo."""

    contract_id: str = Field(
        ...,
        description="The contract ID to get information for, in the format 'principal.contract-name'",
    )


class STXGetContractInfoTool(BaseTool):
    """Tool for getting information about a Stacks contract."""

    name: str = "stacks_get_contract_info"
    description: str = (
        "A tool that can be used to get information about a Stacks smart contract"
    )
    args_schema: Type[BaseModel] = STXGetContractInfoInput
    return_direct: bool = False

    def _deploy(self, contract_id: str) -> str:
        """Get information about a Stacks contract.

        Args:
            contract_id: The contract ID to get information for

        Returns:
            str: The contract information
        """
        from lib.hiro import HiroApi

        api = HiroApi()
        return str(api.get_contract_by_id(contract_id))

    def _run(self, contract_id: str) -> str:
        """Get information about a Stacks contract."""
        return self._deploy(contract_id=contract_id)

    async def _arun(self, contract_id: str) -> str:
        """Async implementation of getting contract information."""
        return self._deploy(contract_id=contract_id)
