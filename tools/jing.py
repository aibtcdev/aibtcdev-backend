from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, Field
from crewai_tools import BaseTool
from .bun import BunScriptRunner

# Schema definitions
class JingGetOrderBookSchema(BaseModel):
    """Input schema for getting orderbook data."""
    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")

class JingCreateBidSchema(BaseModel):
    """Input schema for creating bid offers."""
    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")
    stx_amount: float = Field(..., description="Amount of STX to bid")
    token_amount: float = Field(..., description="Amount of tokens requested")
    recipient: Optional[str] = Field(None, description="Optional: recipient address for private offers")
    expiry: Optional[int] = Field(None, description="Optional: blocks until expiration")

class JingSubmitOrderSchema(BaseModel):
    """Input schema for submitting (accepting) existing orders."""
    swap_id: int = Field(..., description="ID of the order to submit")

class JingCreateAskSchema(BaseModel):
    """Input schema for creating ask offers."""
    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")
    token_amount: float = Field(..., description="Amount of tokens to sell")
    stx_amount: float = Field(..., description="Amount of STX requested")
    recipient: Optional[str] = Field(None, description="Optional: recipient address for private offers")
    expiry: Optional[int] = Field(None, description="Optional: blocks until expiration")

class JingGetPrivateOffersSchema(BaseModel):
    """Input schema for getting private offers."""
    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")
    user_address: str = Field(..., description="Address to check private offers for")

class JingRepriceOrderSchema(BaseModel):
    """Input schema for repricing orders."""
    swap_id: int = Field(..., description="ID of the order to reprice")
    new_amount: float = Field(..., description="New amount (STX for asks, token for bids)")
    pair: str = Field(..., description="Trading pair (e.g., 'PEPE-STX')")
    recipient: Optional[str] = Field(None, description="Optional: recipient address for private offers")
    expiry: Optional[int] = Field(None, description="Optional: blocks until expiration")

class JingGetOrderSchema(BaseModel):
    """Input schema for getting order details."""
    swap_id: int = Field(..., description="ID of the order to get details for")

class JingGetMarketsSchema(BaseModel):
    """Input schema for getting available markets."""
    pass  

# Base Tool with common initialization
class JingBaseTool(BaseTool):
    account_index: Optional[str] = None

    def __init__(self, account_index: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

# Tool implementations
class JingGetOrderBookTool(JingBaseTool):
    name: str = "JingCash: Get Order Book"
    description: str = "Get the current order book for a trading pair"
    args_schema: Type[BaseModel] = JingGetOrderBookSchema

    def _run(self, pair: str):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "get-orderbook.ts",
            pair
        )

class JingCreateBidTool(JingBaseTool):
    name: str = "JingCash: Create Bid"
    description: str = "Create a new bid offer to buy tokens with STX"
    args_schema: Type[BaseModel] = JingCreateBidSchema

    def _run(self, pair: str, stx_amount: float, token_amount: float, 
             recipient: Optional[str] = None, expiry: Optional[int] = None):
        args = [pair, str(stx_amount), str(token_amount)]
        if recipient:
            args.append(recipient)
        if expiry:
            args.append(str(expiry))
        args.append(self.account_index)
        
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "bid.ts",
            *args
        )

class JingSubmitBidTool(JingBaseTool):
    name: str = "JingCash: Submit Bid"
    description: str = "Submit (accept) an existing bid offer to sell tokens"
    args_schema: Type[BaseModel] = JingSubmitOrderSchema

    def _run(self, swap_id: int):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "submit-bid.ts",
            str(swap_id)
        )

class JingCreateAskTool(JingBaseTool):
    name: str = "JingCash: Create Ask"
    description: str = "Create a new ask offer to sell tokens for STX"
    args_schema: Type[BaseModel] = JingCreateAskSchema

    def _run(self, pair: str, token_amount: float, stx_amount: float,
             recipient: Optional[str] = None, expiry: Optional[int] = None):
        args = [pair, str(token_amount), str(stx_amount)]
        if recipient:
            args.append(recipient)
        if expiry:
            args.append(str(expiry))
        args.append(self.account_index)
        
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "ask.ts",
            *args
        )

class JingSubmitAskTool(JingBaseTool):
    name: str = "JingCash: Submit Ask"
    description: str = "Submit (accept) an existing ask offer to buy tokens"
    args_schema: Type[BaseModel] = JingSubmitOrderSchema

    def _run(self, swap_id: int):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "submit-ask.ts",
            str(swap_id)
        )

class JingGetPrivateOffersTool(JingBaseTool):
    name: str = "JingCash: Get Private Offers"
    description: str = "Get private offers for a specific address"
    args_schema: Type[BaseModel] = JingGetPrivateOffersSchema

    def _run(self, pair: str, user_address: str):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "get-private-offers.ts",
            pair,
            user_address
        )

class JingGetPendingOrdersTool(JingBaseTool):
    name: str = "JingCash: Get Pending Orders"
    description: str = "Get all pending orders for the current user"

    def _run(self):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "get-pending-orders.ts"
        )

class JingRepriceBidTool(JingBaseTool):
    name: str = "JingCash: Reprice Bid"
    description: str = "Reprice an existing bid order"
    args_schema: Type[BaseModel] = JingRepriceOrderSchema

    def _run(self, swap_id: int, new_amount: float, pair: str,
             recipient: Optional[str] = None, expiry: Optional[int] = None):
        args = [str(swap_id), str(new_amount), pair]
        if recipient:
            args.append(recipient)
        if expiry:
            args.append(str(expiry))
        args.append(self.account_index)
        
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "reprice-bid.ts",
            *args
        )

class JingRepriceAskTool(JingBaseTool):
    name: str = "JingCash: Reprice Ask"
    description: str = "Reprice an existing ask order"
    args_schema: Type[BaseModel] = JingRepriceOrderSchema

    def _run(self, swap_id: int, new_amount: float, pair: str,
             recipient: Optional[str] = None, expiry: Optional[int] = None):
        args = [str(swap_id), str(new_amount), pair]
        if recipient:
            args.append(recipient)
        if expiry:
            args.append(str(expiry))
        args.append(self.account_index)
        
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "reprice-ask.ts",
            *args
        )

class JingCancelBidTool(JingBaseTool):
    name: str = "JingCash: Cancel Bid"
    description: str = "Cancel an existing bid order"
    args_schema: Type[BaseModel] = JingGetOrderSchema

    def _run(self, swap_id: int):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "cancel-bid.ts",
            str(swap_id)
        )

class JingCancelAskTool(JingBaseTool):
    name: str = "JingCash: Cancel Ask"
    description: str = "Cancel an existing ask order"
    args_schema: Type[BaseModel] = JingGetOrderSchema

    def _run(self, swap_id: int):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "cancel-ask.ts",
            str(swap_id)
        )

class JingGetBidTool(JingBaseTool):
    name: str = "JingCash: Get Bid Details"
    description: str = "Get details of a specific bid order"
    args_schema: Type[BaseModel] = JingGetOrderSchema

    def _run(self, swap_id: int):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "get-bid.ts",
            str(swap_id)
        )

class JingGetAskTool(JingBaseTool):
    name: str = "JingCash: Get Ask Details"
    description: str = "Get details of a specific ask order"
    args_schema: Type[BaseModel] = JingGetOrderSchema

    def _run(self, swap_id: int):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "get-ask.ts",
            str(swap_id)
        )
    
class JingGetMarketsTool(JingBaseTool):
    name: str = "JingCash: Get Available Markets"
    description: str = "Get all available trading pairs and their contract details"
    args_schema: Type[BaseModel] = JingGetMarketsSchema

    def _run(self):
        return BunScriptRunner.bun_run(
            self.account_index,
            "jing",
            "list-markets.ts"
        )