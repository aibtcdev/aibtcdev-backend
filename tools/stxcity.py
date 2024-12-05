from typing import Dict
from crewai.tools import BaseTool
from .bun import BunScriptRunner
from pydantic import BaseModel, Field


class STXCityBondingToolSchema(BaseModel):
    """Parameters for STX City bonding tool"""
    token_symbol: str = Field(...,
        description="The symbol for the token (e.g., 'CITY')"
    )
    token_name: str = Field(...,
        description="The name of the token (e.g., 'STX City Token')"
    )
    token_max_supply: str = Field(...,
        description="The maximum supply of tokens"
    )
    token_decimals: str = Field(...,
        description="The number of decimal places for the token"
    )
    token_uri: str = Field(...,
        description="The URI for the token metadata"
    )

class STXCityBondingTool(BaseTool):
    name: str = "STXCityBondingTool"
    description: str = """
    Deploy a new token with bonding curve on STX City.
    This tool creates a new token with specified parameters and sets up a bonding curve for it.
    
    Parameters:
    - token_symbol: The symbol for the token (e.g., 'CITY')
    - token_name: The name of the token (e.g., 'STX City Token')
    - token_max_supply: The maximum supply of tokens
    - token_decimals: The number of decimal places for the token
    - token_uri: The URI for the token metadata
    
    Example:
    {
        "token_symbol": "CITY",
        "token_name": "STX City Token",
        "token_max_supply": "1000000",
        "token_decimals": "6",
        "token_uri": "https://stxcity.xyz/token/metadata"
    }
    """
    args_schema: type[BaseModel] = STXCityBondingToolSchema
    account_index: str = "0"


    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index


    def _run(self, 
                token_symbol: str,
                token_name: str,
                token_max_supply: str,
                token_decimals: str,
                token_uri: str) -> Dict[str, str | bool | None]:
        """
        Execute the STX City bonding curve deployment command
        """
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-stxcity",
            "deploy-package.ts",
            token_symbol,
            token_name,
            token_max_supply,
            token_decimals,
            token_uri,
        )