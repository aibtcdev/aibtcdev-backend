from typing import Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from backend.models import UUID
from tools.bun import BunScriptRunner


class FaktoryBaseInput(BaseModel):
    """Base input schema for Faktory tools that don't require parameters."""

    pass


class FaktoryExecuteBuyInput(BaseModel):
    """Input schema for Faktory buy order execution."""

    btc_amount: str = Field(
        ...,
        description="Amount of BTC to spend on the purchase in standard units (e.g. 0.0004 = 0.0004 BTC or 40000 sats)",
    )
    dao_token_dex_contract_address: str = Field(
        ..., description="Contract principal where the DAO token is listed"
    )
    slippage: Optional[str] = Field(
        default="15",
        description="Slippage tolerance in basis points (default: 15, which is 0.15%)",
    )


class FaktoryExecuteBuyTool(BaseTool):
    name: str = "faktory_execute_buy"
    description: str = (
        "Execute a buy order on Faktory DEX with specified BTC amount and token details"
    )
    args_schema: Type[BaseModel] = FaktoryExecuteBuyInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        btc_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "exec-buy.ts",
            btc_amount,
            dao_token_dex_contract_address,
            slippage,
        )

    def _run(
        self,
        btc_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order."""
        return self._deploy(btc_amount, dao_token_dex_contract_address, slippage)

    async def _arun(
        self,
        btc_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order (async)."""
        return self._deploy(btc_amount, dao_token_dex_contract_address, slippage)


class FaktoryExecuteBuyStxInput(BaseModel):
    """Input schema for Faktory buy order execution."""

    stx_amount: str = Field(
        ...,
        description="Amount of STX to spend on the purchase in standard units (e.g. 1.5 = 1.5 STX)",
    )
    dao_token_dex_contract_address: str = Field(
        ..., description="Contract principal where the DAO token is listed"
    )
    slippage: Optional[str] = Field(
        default="15",
        description="Slippage tolerance in percentage (default: 15%)",
    )


class FaktoryExecuteBuyStxTool(BaseTool):
    name: str = "faktory_execute_buy_stx"
    description: str = (
        "Execute a buy order on Faktory DEX with specified STX amount and token details"
    )
    args_schema: Type[BaseModel] = FaktoryExecuteBuyStxInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        stx_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "exec-buy-stx.ts",
            stx_amount,
            dao_token_dex_contract_address,
            slippage,
        )

    def _run(
        self,
        stx_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order."""
        return self._deploy(stx_amount, dao_token_dex_contract_address, slippage)

    async def _arun(
        self,
        stx_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order (async)."""
        return self._deploy(stx_amount, dao_token_dex_contract_address, slippage)


class FaktoryExecuteSellInput(BaseModel):
    """Input schema for Faktory sell order execution."""

    token_amount: str = Field(
        ...,
        description="Amount of tokens to sell in standard units (e.g. 1.5 = 1.5 tokens)",
    )
    dao_token_dex_contract_address: str = Field(
        ..., description="Contract principal where the DAO token is listed"
    )
    slippage: Optional[str] = Field(
        default="15",
        description="Slippage tolerance in percentage (default: 15%)",
    )


class FaktoryExecuteSellTool(BaseTool):
    name: str = "faktory_execute_sell"
    description: str = "Execute a sell order on Faktory DEX with specified token amount and DEX details"
    args_schema: Type[BaseModel] = FaktoryExecuteSellInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        token_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a sell order."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "exec-sell.ts",
            token_amount,
            dao_token_dex_contract_address,
            slippage,
        )

    def _run(
        self,
        token_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a sell order."""
        return self._deploy(token_amount, dao_token_dex_contract_address, slippage)

    async def _arun(
        self,
        token_amount: str,
        dao_token_dex_contract_address: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to place a sell order (async)."""
        return self._deploy(token_amount, dao_token_dex_contract_address, slippage)


class FaktoryGetBuyQuoteInput(BaseModel):
    """Input schema for getting a Faktory buy quote."""

    stx_amount: str = Field(
        ..., description="Amount of STX to spend in standard units (e.g. 1.5 = 1.5 STX)"
    )
    dex_contract_id: str = Field(..., description="Contract ID of the DEX")
    slippage: Optional[str] = Field(
        default="15",
        description="Slippage tolerance in percentage (default: 15%)",
    )


class FaktoryGetBuyQuoteTool(BaseTool):
    name: str = "faktory_get_buy_quote"
    description: str = (
        "Get a quote for buying tokens on Faktory DEX with specified STX amount"
    )
    args_schema: Type[BaseModel] = FaktoryGetBuyQuoteInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        stx_amount: str,
        dex_contract_id: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to get a buy quote."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "get-buy-quote.ts",
            stx_amount,
            dex_contract_id,
            slippage,
        )

    def _run(
        self,
        stx_amount: str,
        dex_contract_id: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to get a buy quote."""
        return self._deploy(stx_amount, dex_contract_id, slippage)

    async def _arun(
        self,
        stx_amount: str,
        dex_contract_id: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to get a buy quote (async)."""
        return self._deploy(stx_amount, dex_contract_id, slippage)


class FaktoryGetDaoTokensInput(BaseModel):
    """Input schema for getting DAO tokens from Faktory."""

    page: Optional[str] = Field(
        default="1",
        description="Page number for pagination",
    )
    limit: Optional[str] = Field(
        default="10",
        description="Number of items per page",
    )
    search: Optional[str] = Field(
        default="",
        description="Search term to filter tokens",
    )
    sort_order: Optional[str] = Field(
        default="",
        description="Sort order for the results",
    )


class FaktoryGetDaoTokensTool(BaseTool):
    name: str = "faktory_get_dao_tokens"
    description: str = "Get a list of DAO tokens from Faktory with optional pagination, search, and sorting"
    args_schema: Type[BaseModel] = FaktoryGetDaoTokensInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        page: Optional[str] = "1",
        limit: Optional[str] = "10",
        search: Optional[str] = "",
        sort_order: Optional[str] = "",
        **kwargs,
    ) -> str:
        """Execute the tool to get DAO tokens."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "get-dao-tokens.ts",
            page,
            limit,
            search,
            sort_order,
        )

    def _run(
        self,
        page: Optional[str] = "1",
        limit: Optional[str] = "10",
        search: Optional[str] = "",
        sort_order: Optional[str] = "",
        **kwargs,
    ) -> str:
        """Execute the tool to get DAO tokens."""
        return self._deploy(page, limit, search, sort_order)

    async def _arun(
        self,
        page: Optional[str] = "1",
        limit: Optional[str] = "10",
        search: Optional[str] = "",
        sort_order: Optional[str] = "",
        **kwargs,
    ) -> str:
        """Execute the tool to get DAO tokens (async)."""
        return self._deploy(page, limit, search, sort_order)


class FaktoryGetSellQuoteInput(BaseModel):
    """Input schema for getting a Faktory sell quote."""

    token_amount: str = Field(
        ...,
        description="Amount of tokens to sell in standard units (e.g. 1.5 = 1.5 tokens)",
    )
    dex_contract_id: str = Field(..., description="Contract ID of the DEX")
    slippage: Optional[str] = Field(
        default="15",
        description="Slippage tolerance in percentage (default: 15%)",
    )


class FaktoryGetSellQuoteTool(BaseTool):
    name: str = "faktory_get_sell_quote"
    description: str = (
        "Get a quote for selling tokens on Faktory DEX with specified token amount"
    )
    args_schema: Type[BaseModel] = FaktoryGetSellQuoteInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        token_amount: str,
        dex_contract_id: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to get a sell quote."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "get-sell-quote.ts",
            token_amount,
            dex_contract_id,
            slippage,
        )

    def _run(
        self,
        token_amount: str,
        dex_contract_id: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to get a sell quote."""
        return self._deploy(token_amount, dex_contract_id, slippage)

    async def _arun(
        self,
        token_amount: str,
        dex_contract_id: str,
        slippage: Optional[str] = "15",
        **kwargs,
    ) -> str:
        """Execute the tool to get a sell quote (async)."""
        return self._deploy(token_amount, dex_contract_id, slippage)


class FaktoryGetTokenInput(BaseModel):
    """Input schema for getting token information from Faktory."""

    dex_contract_id: str = Field(..., description="Contract ID of the DEX")


class FaktoryGetTokenTool(BaseTool):
    name: str = "faktory_get_token"
    description: str = "Get detailed information about a token from its DEX contract"
    args_schema: Type[BaseModel] = FaktoryGetTokenInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dex_contract_id: str,
        **kwargs,
    ) -> str:
        """Execute the tool to get token information."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "get-token.ts",
            dex_contract_id,
        )

    def _run(
        self,
        dex_contract_id: str,
        **kwargs,
    ) -> str:
        """Execute the tool to get token information."""
        return self._deploy(dex_contract_id)

    async def _arun(
        self,
        dex_contract_id: str,
        **kwargs,
    ) -> str:
        """Execute the tool to get token information (async)."""
        return self._deploy(dex_contract_id)


class FaktoryGetSbtcBaseInput(BaseModel):
    """Base input schema for Faktory sBTC faucet that doesn't require parameters."""

    pass


class FaktoryGetSbtcTool(BaseTool):
    name: str = "faktory_get_sbtc"
    description: str = "Request testnet sBTC from the Faktory faucet"
    args_schema: Type[BaseModel] = FaktoryGetSbtcBaseInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, **kwargs) -> str:
        """Execute the tool to request testnet sBTC from the faucet."""
        if self.wallet_id is None:
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "get-faktory-sbtc.ts",
        )

    def _run(self, **kwargs) -> str:
        """Execute the tool to request testnet sBTC from the faucet."""
        return self._deploy()

    async def _arun(self, **kwargs) -> str:
        """Execute the tool to request testnet sBTC from the faucet (async)."""
        return self._deploy()
