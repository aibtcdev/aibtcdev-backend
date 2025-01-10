import requests
from langchain.tools import BaseTool
from lib.lunarcrush import LunarcrushApi
from pydantic import BaseModel, Field
from typing import Type


class LunarCrushTokenMetricsInput(BaseModel):
    """Input schema for LunarCrushTokenMetrics tool."""

    token_symbol: str = Field(..., description="The token symbol")


class LunarCrushTokenMetricsTool(BaseTool):
    name: str = "lunarcrush_token_metrics"
    description: str = (
        "Fetch social metrics for a specific cryptocurrency token from LunarCrush API. "
        "Metrics include Galaxy Score™, AltRank™, price, volatility, 24h percent change, "
        "market cap, social mentions, social interactions, social contributors, social "
        "dominance, and categories."
    )
    args_schema: Type[BaseModel] = LunarCrushTokenMetricsInput
    return_direct: bool = False

    def _deploy(self, token_symbol: str, **kwargs) -> str:
        """Execute the tool to fetch token social metrics."""
        try:
            obj = LunarcrushApi()
            return obj.get_token_socials(token_symbol)

        except requests.RequestException as e:
            return f"Error fetching token data: {e}"

    def _run(self, token_symbol: str, **kwargs) -> str:
        """Execute the tool to fetch token social metrics."""
        return self._deploy(token_symbol, **kwargs)

    async def _arun(self, token_symbol: str, **kwargs) -> str:
        """Async version of the tool."""
        return self._deploy(token_symbol, **kwargs)


class LunarCrushTokenMetadataInput(BaseModel):
    """Input schema for LunarCrushTokenMetadata tool."""

    token_symbol: str = Field(..., description="The token symbol")


class LunarCrushTokenMetadataTool(BaseTool):
    name: str = "lunarcrush_token_metadata"
    description: str = (
        "Fetch metadata and project information for a specific cryptocurrency token "
        "from LunarCrush API"
    )
    args_schema: Type[BaseModel] = LunarCrushTokenMetadataInput
    return_direct: bool = False

    def _deploy(self, token_symbol: str, **kwargs) -> str:
        """Execute the tool to fetch token metadata."""
        try:
            obj = LunarcrushApi()
            return obj.get_token_metadata(token_symbol)

        except requests.RequestException as e:
            return f"Error fetching token data: {e}"

    def _run(self, token_symbol: str, **kwargs) -> str:
        """Execute the tool to fetch token metadata."""
        return self._deploy(token_symbol, **kwargs)

    async def _arun(self, token_symbol: str, **kwargs) -> str:
        """Async version of the tool."""
        return self._deploy(token_symbol, **kwargs)


class SearchLunarCrushInput(BaseModel):
    """Input schema for SearchLunarCrush tool."""

    term: str = Field(..., description="A term to search for.")


class SearchLunarCrushTool(BaseTool):
    name: str = "lunarcrush_search"
    description: str = (
        "Search for recently popular social media posts matching a specific search term "
        "or phrase using LunarCrush API"
    )
    args_schema: Type[BaseModel] = SearchLunarCrushInput
    return_direct: bool = False

    def _deploy(self, term: str, **kwargs) -> str:
        """Execute the tool to search social posts."""
        try:
            obj = LunarcrushApi()
            return obj.search(term)

        except requests.RequestException as e:
            return f"Error searching data: {e}"

    def _run(self, term: str, **kwargs) -> str:
        """Execute the tool to search social posts."""
        return self._deploy(term, **kwargs)

    async def _arun(self, term: str, **kwargs) -> str:
        """Async version of the tool."""
        return self._deploy(term, **kwargs)
