import requests
from crewai_tools import BaseTool
from lib.lunarcrush import LunarcrushApi
from pydantic import BaseModel, Field
from typing import Type


class LunarCrushTokenMetricsToolSchema(BaseModel):
    """Input for LunarCrushTokenMetricsTool tool."""

    token_symbol: str = Field(..., description="The token symbol")


class LunarCrushTokenMetricsTool(BaseTool):
    name: str = "Scrape crypto token social metrics from LunarCrush"
    description: str = (
        "A tool that can be used to fetches data for a specific token from LunarCrush API."
        "Metrics include Galaxy Score™, AltRank™, price, volatility, 24h percent change, market cap, social mentions, social interactions, social contributors, social dominance, and categories."
    )
    args_schema: Type[BaseModel] = LunarCrushTokenMetricsToolSchema

    def _run(self, token_symbol: str) -> str:
        try:
            obj = LunarcrushApi()
            return obj.get_token_socials(token_symbol)

        except requests.RequestException as e:
            return f"Error fetching token data: {e}"


class LunarCrushTokenMetadataToolSchema(BaseModel):
    """Input for LunarCrushTokenMetadataTool tool."""

    token_symbol: str = Field(..., description="The token symbol")


class LunarCrushTokenMetadataTool(BaseTool):
    name: str = "Get meta information for a cryptocurrency project on Lunarcrush"
    description: str = (
        "A tool that can be used to fetches metadata for a specific token from LunarCrush API."
    )
    args_schema: Type[BaseModel] = LunarCrushTokenMetadataToolSchema

    def _run(self, token_symbol: str) -> str:
        try:
            obj = LunarcrushApi()
            return obj.get_token_metadata(token_symbol)

        except requests.RequestException as e:
            return f"Error fetching token data: {e}"


class SearchLunarCrushToolSchema(BaseModel):
    """Input for SearchLunarCrushTool tool."""

    term: str = Field(..., description="A term to search for.")


class SearchLunarCrushTool(BaseTool):
    name: str = "Search for social posts matching a single search term or phrase."
    description: str = (
        "Get recently popular social posts matching a single search term or phrase."
    )
    args_schema: Type[BaseModel] = SearchLunarCrushToolSchema

    def _run(self, term: str) -> str:
        try:
            obj = LunarcrushApi()
            return obj.search(term)

        except requests.RequestException as e:
            return f"Error searching data: {e}"
