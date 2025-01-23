from .bun import BunScriptRunner
from backend.models import UUID
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Type


# Schema definitions
class JingGetOrderBookInput(BaseModel):
    """Input schema for getting orderbook data."""

    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")


class JingCreateBidInput(BaseModel):
    """Input schema for creating bid offers."""

    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")
    stx_amount: float = Field(..., description="Amount of STX to bid")
    token_amount: float = Field(..., description="Amount of tokens requested")
    recipient: Optional[str] = Field(
        None, description="Optional: recipient address for private offers"
    )
    expiry: Optional[int] = Field(None, description="Optional: blocks until expiration")


class JingSubmitOrderInput(BaseModel):
    """Input schema for submitting (accepting) existing orders."""

    swap_id: int = Field(..., description="ID of the order to submit")


class JingCreateAskInput(BaseModel):
    """Input schema for creating ask offers."""

    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")
    token_amount: float = Field(..., description="Amount of tokens to sell")
    stx_amount: float = Field(..., description="Amount of STX requested")
    recipient: Optional[str] = Field(
        None, description="Optional: recipient address for private offers"
    )
    expiry: Optional[int] = Field(None, description="Optional: blocks until expiration")


class JingGetPrivateOffersInput(BaseModel):
    """Input schema for getting private offers."""

    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")
    user_address: str = Field(..., description="Address to check private offers for")


class JingRepriceOrderInput(BaseModel):
    """Input schema for repricing orders."""

    swap_id: int = Field(..., description="ID of the order to reprice")
    new_amount: float = Field(
        ..., description="New amount (STX for asks, token for bids)"
    )
    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")
    recipient: Optional[str] = Field(
        None, description="Optional: recipient address for private offers"
    )
    expiry: Optional[int] = Field(None, description="Optional: blocks until expiration")


class JingGetOrderInput(BaseModel):
    """Input schema for getting order details."""

    swap_id: int = Field(..., description="ID of the order to get details for")


class JingGetMarketsInput(BaseModel):
    """Input schema for getting available markets."""

    pass


# Base Tool with common initialization
class JingBaseTool(BaseTool):
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id


# Tool implementations
class JingGetOrderBookTool(JingBaseTool):
    name: str = "jing_get_order_book"
    description: str = "Get the current order book for a trading pair on JingCash"
    args_schema: Type[BaseModel] = JingGetOrderBookInput
    return_direct: bool = False

    def _deploy(self, pair: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get order book data."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(self.wallet_id, "jing", "get-orderbook.ts", pair)

    def _run(self, pair: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get order book data."""
        return self._deploy(pair, **kwargs)

    async def _arun(self, pair: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(pair, **kwargs)


class JingCreateBidTool(JingBaseTool):
    name: str = "jing_create_bid"
    description: str = "Create a new bid offer to buy tokens with STX on JingCash"
    args_schema: Type[BaseModel] = JingCreateBidInput
    return_direct: bool = False

    def _deploy(
        self,
        pair: str,
        stx_amount: float,
        token_amount: float,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create a bid offer."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        args = [pair, str(stx_amount), str(token_amount)]
        if recipient:
            args.append(recipient)
        if expiry:
            args.append(str(expiry))
        args.append(str(self.wallet_id))

        return BunScriptRunner.bun_run(self.wallet_id, "jing", "bid.ts", *args)

    def _run(
        self,
        pair: str,
        stx_amount: float,
        token_amount: float,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create a bid offer."""
        return self._deploy(pair, stx_amount, token_amount, recipient, expiry, **kwargs)

    async def _arun(
        self,
        pair: str,
        stx_amount: float,
        token_amount: float,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(pair, stx_amount, token_amount, recipient, expiry)


class JingSubmitBidTool(JingBaseTool):
    name: str = "jing_submit_bid"
    description: str = (
        "Submit (accept) an existing bid offer to sell tokens on JingCash"
    )
    args_schema: Type[BaseModel] = JingSubmitOrderInput
    return_direct: bool = False

    def _deploy(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to submit a bid."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id, "jing", "submit-bid.ts", str(swap_id)
        )

    def _run(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to submit a bid."""
        return self._deploy(swap_id, **kwargs)

    async def _arun(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(swap_id, **kwargs)


class JingCreateAskTool(JingBaseTool):
    name: str = "jing_create_ask"
    description: str = "Create a new ask offer to sell tokens for STX on JingCash"
    args_schema: Type[BaseModel] = JingCreateAskInput
    return_direct: bool = False

    def _deploy(
        self,
        pair: str,
        token_amount: float,
        stx_amount: float,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create an ask offer."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        args = [pair, str(token_amount), str(stx_amount)]
        if recipient:
            args.append(recipient)
        if expiry:
            args.append(str(expiry))
        args.append(str(self.wallet_id))

        return BunScriptRunner.bun_run(self.wallet_id, "jing", "ask.ts", *args)

    def _run(
        self,
        pair: str,
        token_amount: float,
        stx_amount: float,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create an ask offer."""
        return self._deploy(pair, token_amount, stx_amount, recipient, expiry, **kwargs)

    async def _arun(
        self,
        pair: str,
        token_amount: float,
        stx_amount: float,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(pair, token_amount, stx_amount, recipient, expiry)


class JingSubmitAskTool(JingBaseTool):
    name: str = "jing_submit_ask"
    description: str = "Submit (accept) an existing ask offer to buy tokens on JingCash"
    args_schema: Type[BaseModel] = JingSubmitOrderInput
    return_direct: bool = False

    def _deploy(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to submit an ask."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id, "jing", "submit-ask.ts", str(swap_id)
        )

    def _run(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to submit an ask."""
        return self._deploy(swap_id, **kwargs)

    async def _arun(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(swap_id, **kwargs)


class JingGetPrivateOffersTool(JingBaseTool):
    name: str = "jing_get_private_offers"
    description: str = "Get private offers for a specific address on JingCash"
    args_schema: Type[BaseModel] = JingGetPrivateOffersInput
    return_direct: bool = False

    def _deploy(self, pair: str, user_address: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get private offers."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id, "jing", "get-private-offers.ts", pair, user_address
        )

    def _run(self, pair: str, user_address: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get private offers."""
        return self._deploy(pair, user_address, **kwargs)

    async def _arun(self, pair: str, user_address: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(pair, user_address, **kwargs)


class JingGetPendingOrdersTool(JingBaseTool):
    name: str = "jing_get_pending_orders"
    description: str = "Get all pending orders for the current user on JingCash"
    args_schema: Type[BaseModel] = JingGetMarketsInput
    return_direct: bool = False

    def _deploy(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get pending orders."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(self.wallet_id, "jing", "get-pending-orders.ts")

    def _run(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get pending orders."""
        return self._deploy(**kwargs)

    async def _arun(self, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(**kwargs)


class JingRepriceBidTool(JingBaseTool):
    name: str = "jing_reprice_bid"
    description: str = "Reprice an existing bid order on JingCash"
    args_schema: Type[BaseModel] = JingRepriceOrderInput
    return_direct: bool = False

    def _deploy(
        self,
        swap_id: int,
        new_amount: float,
        pair: str,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to reprice a bid."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        args = [str(swap_id), str(new_amount), pair]
        if recipient:
            args.append(recipient)
        if expiry:
            args.append(str(expiry))
        args.append(str(self.wallet_id))

        return BunScriptRunner.bun_run(self.wallet_id, "jing", "reprice-bid.ts", *args)

    def _run(
        self,
        swap_id: int,
        new_amount: float,
        pair: str,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to reprice a bid."""
        return self._deploy(swap_id, new_amount, pair, recipient, expiry, **kwargs)

    async def _arun(
        self,
        swap_id: int,
        new_amount: float,
        pair: str,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(swap_id, new_amount, pair, recipient, expiry, **kwargs)


class JingRepriceAskTool(JingBaseTool):
    name: str = "jing_reprice_ask"
    description: str = "Reprice an existing ask order on JingCash"
    args_schema: Type[BaseModel] = JingRepriceOrderInput
    return_direct: bool = False

    def _deploy(
        self,
        swap_id: int,
        new_amount: float,
        pair: str,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to reprice an ask."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        args = [str(swap_id), str(new_amount), pair]
        if recipient:
            args.append(recipient)
        if expiry:
            args.append(str(expiry))
        args.append(str(self.wallet_id))

        return BunScriptRunner.bun_run(self.wallet_id, "jing", "reprice-ask.ts", *args)

    def _run(
        self,
        swap_id: int,
        new_amount: float,
        pair: str,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to reprice an ask."""
        return self._deploy(swap_id, new_amount, pair, recipient, expiry, **kwargs)

    async def _arun(
        self,
        swap_id: int,
        new_amount: float,
        pair: str,
        recipient: Optional[str] = None,
        expiry: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(swap_id, new_amount, pair, recipient, expiry, **kwargs)


class JingCancelBidTool(JingBaseTool):
    name: str = "jing_cancel_bid"
    description: str = "Cancel an existing bid order on JingCash"
    args_schema: Type[BaseModel] = JingGetOrderInput
    return_direct: bool = False

    def _deploy(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to cancel a bid."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id, "jing", "cancel-bid.ts", str(swap_id)
        )

    def _run(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to cancel a bid."""
        return self._deploy(swap_id, **kwargs)

    async def _arun(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(swap_id, **kwargs)


class JingCancelAskTool(JingBaseTool):
    name: str = "jing_cancel_ask"
    description: str = "Cancel an existing ask order on JingCash"
    args_schema: Type[BaseModel] = JingGetOrderInput
    return_direct: bool = False

    def _deploy(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to cancel an ask."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id, "jing", "cancel-ask.ts", str(swap_id)
        )

    def _run(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to cancel an ask."""
        return self._deploy(swap_id, **kwargs)

    async def _arun(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(swap_id, **kwargs)


class JingGetBidTool(JingBaseTool):
    name: str = "jing_get_bid"
    description: str = "Get details of a specific bid order on JingCash"
    args_schema: Type[BaseModel] = JingGetOrderInput
    return_direct: bool = False

    def _deploy(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get bid details."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id, "jing", "get-bid.ts", str(swap_id)
        )

    def _run(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get bid details."""
        return self._deploy(swap_id, **kwargs)

    async def _arun(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(swap_id, **kwargs)


class JingGetAskTool(JingBaseTool):
    name: str = "jing_get_ask"
    description: str = "Get details of a specific ask order on JingCash"
    args_schema: Type[BaseModel] = JingGetOrderInput
    return_direct: bool = False

    def _deploy(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get ask details."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id, "jing", "get-ask.ts", str(swap_id)
        )

    def _run(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get ask details."""
        return self._deploy(swap_id, **kwargs)

    async def _arun(self, swap_id: int, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(swap_id, **kwargs)


class JingGetMarketsTool(JingBaseTool):
    name: str = "jing_get_markets"
    description: str = (
        "Get all available trading pairs and their contract details on JingCash"
    )
    args_schema: Type[BaseModel] = JingGetMarketsInput
    return_direct: bool = False

    def _deploy(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get available markets."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(self.wallet_id, "jing", "list-markets.ts")

    def _run(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get available markets."""
        return self._deploy(**kwargs)

    async def _arun(self, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(**kwargs)
