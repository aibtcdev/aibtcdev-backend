from decimal import Decimal
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from tools.bun import BunScriptRunner
from typing import Any, Dict, Optional, Type, Union


class StxCityBaseInput(BaseModel):
    """Base input schema for STXCity tools that don't require parameters."""

    pass


class StxCityExecuteBuyInput(BaseModel):
    """Input schema for STXCity buy order execution."""

    stx_amount: Decimal = Field(
        ..., description="Amount of STX to spend on the purchase"
    )
    dex_contract_id: str = Field(..., description="Contract ID of the DEX")
    token_contract_id: str = Field(
        ..., description="Contract ID of the token to purchase"
    )
    token_symbol: str = Field(..., description="Symbol of the token to purchase")
    slippage: Optional[int] = Field(
        default=50,
        description="Slippage tolerance in basis points (default: 50, which is 0.5%)",
    )


class StxCityExecuteBuyTool(BaseTool):
    name: str = "stxcity_execute_buy"
    description: str = (
        "Execute a buy order on STXCity DEX with specified STX amount and token details"
    )
    args_schema: Type[BaseModel] = StxCityExecuteBuyInput
    return_direct: bool = False
    account_index: str = "0"

    def __init__(self, account_index: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _deploy(
        self,
        stx_amount: Decimal,
        dex_contract_id: str,
        token_contract_id: str,
        token_symbol: str,
        slippage: Optional[int] = 50,
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order."""
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-stxcity",
            "exec-buy.ts",
            stx_amount,
            dex_contract_id,
            token_contract_id,
            token_symbol,
            slippage,
        )

    def _run(
        self,
        stx_amount: Decimal,
        dex_contract_id: str,
        token_contract_id: str,
        token_symbol: str,
        slippage: Optional[int] = 50,
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order."""
        return self._deploy(
            stx_amount, dex_contract_id, token_contract_id, token_symbol, slippage
        )

    async def _arun(
        self,
        stx_amount: Decimal,
        dex_contract_id: str,
        token_contract_id: str,
        token_symbol: str,
        slippage: Optional[int] = 50,
        **kwargs,
    ) -> str:
        """Async version of the tool."""
        return self._deploy(
            stx_amount, dex_contract_id, token_contract_id, token_symbol, slippage
        )


class StxCityCheckValidBondingInput(BaseModel):
    """Input schema for checking valid bonding contracts."""

    dex_contract_id: str = Field(..., description="Contract ID of the DEX")
    token_contract_id: str = Field(..., description="Contract ID of the token")


class StxCityCheckValidBondingTool(BaseTool):
    name: str = "stxcity_check_valid_bonding"
    description: str = (
        "Check if the given DEX and token contracts are valid for bonding on STXCity"
    )
    args_schema: Type[BaseModel] = StxCityCheckValidBondingInput
    return_direct: bool = False
    account_index: str = "0"

    def __init__(self, account_index: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _deploy(
        self,
        dex_contract_id: str,
        token_contract_id: str,
        **kwargs,
    ) -> str:
        """Execute the tool to validate bonding contracts."""
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-stxcity",
            "exec-check.ts",
            dex_contract_id,
            token_contract_id,
        )

    def _run(
        self,
        dex_contract_id: str,
        token_contract_id: str,
        **kwargs,
    ) -> str:
        """Execute the tool to validate bonding contracts."""
        return self._deploy(dex_contract_id, token_contract_id)

    async def _arun(
        self,
        dex_contract_id: str,
        token_contract_id: str,
        **kwargs,
    ) -> str:
        """Async version of the tool."""
        return self._deploy(dex_contract_id, token_contract_id)


class StxCityListBondingTokensTool(BaseTool):
    name: str = "stxcity_list_bonding_tokens"
    description: str = "Get a list of all available tokens for bonding on STXCity"
    args_schema: Type[BaseModel] = StxCityBaseInput
    return_direct: bool = False
    account_index: str = "0"

    def __init__(self, account_index: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _deploy(self, **kwargs) -> str:
        """Execute the tool to list available bonding tokens."""
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-stxcity",
            "exec-list.ts",
        )

    def _run(self, **kwargs) -> str:
        """Execute the tool to list available bonding tokens."""
        return self._deploy()

    async def _arun(self, **kwargs) -> str:
        """Async version of the tool."""
        return self._deploy()


class StxCitySearchInput(BaseModel):
    """Input schema for searching bonding opportunities."""

    keyword: Optional[str] = Field(
        default=None, description="Search keyword to filter results"
    )
    token_contract: Optional[str] = Field(
        default=None, description="Token contract to filter results"
    )


class StxCitySearchTool(BaseTool):
    name: str = "stxcity_search"
    description: str = (
        "Search for bonding opportunities on STXCity with optional keyword and token "
        "contract filters"
    )
    args_schema: Type[BaseModel] = StxCitySearchInput
    return_direct: bool = False
    account_index: str = "0"

    def __init__(self, account_index: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _deploy(
        self,
        keyword: Optional[str] = None,
        token_contract: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Execute the tool to search for bonding opportunities."""
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-stxcity",
            "exec-search.ts",
            keyword or "",
            token_contract or "",
        )

    def _run(
        self,
        keyword: Optional[str] = None,
        token_contract: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Execute the tool to search for bonding opportunities."""
        return self._deploy(keyword, token_contract)

    async def _arun(
        self,
        keyword: Optional[str] = None,
        token_contract: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Async version of the tool."""
        return self._deploy(keyword, token_contract)


class StxCityExecuteSellInput(BaseModel):
    """Input schema for STXCity sell order execution."""

    token_amount: Decimal = Field(..., description="Amount of tokens to sell")
    dex_contract_id: str = Field(..., description="Contract ID of the DEX")
    token_contract_id: str = Field(..., description="Contract ID of the token to sell")
    token_symbol: str = Field(..., description="Symbol of the token to sell")
    slippage: Optional[int] = Field(
        default=50,
        description="Slippage tolerance in basis points (default: 50, which is 0.5%)",
    )


class StxCityExecuteSellTool(BaseTool):
    name: str = "stxcity_execute_sell"
    description: str = (
        "Execute a sell order on STXCity DEX with specified token amount and details"
    )
    args_schema: Type[BaseModel] = StxCityExecuteSellInput
    return_direct: bool = False
    account_index: str = "0"

    def __init__(self, account_index: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _deploy(
        self,
        token_amount: Decimal,
        dex_contract_id: str,
        token_contract_id: str,
        token_symbol: str,
        slippage: Optional[int] = 50,
        **kwargs,
    ) -> str:
        """Execute the tool to place a sell order."""
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-stxcity",
            "exec-sell.ts",
            token_amount,
            dex_contract_id,
            token_contract_id,
            token_symbol,
            slippage,
        )

    def _run(
        self,
        token_amount: Decimal,
        dex_contract_id: str,
        token_contract_id: str,
        token_symbol: str,
        slippage: Optional[int] = 50,
        **kwargs,
    ) -> str:
        """Execute the tool to place a sell order."""
        return self._deploy(
            token_amount, dex_contract_id, token_contract_id, token_symbol, slippage
        )

    async def _arun(
        self,
        token_amount: Decimal,
        dex_contract_id: str,
        token_contract_id: str,
        token_symbol: str,
        slippage: Optional[int] = 50,
        **kwargs,
    ) -> str:
        """Async version of the tool."""
        return self._deploy(
            token_amount, dex_contract_id, token_contract_id, token_symbol, slippage
        )