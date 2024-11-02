# from .get_btc_data import GetBitcoinData
from crewai_tools import SerperDevTool

from .velar import VelarGetPriceHistory, VelarGetTokens
from .wallet import WalletGetMyAddress, WalletGetMyBalance
from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowGetAvailableTokens, BitflowExecuteTradeTool
from .lunarcrush import (
    LunarCrushTokenMetricsTool,
    SearchLunarCrushTool,
    LunarCrushTokenMetadataTool,
)
from .transactions import (
    StacksTransactionStatusTool,
    StacksTransactionTool,
    StacksTransactionByAddressTool,
)


# from .fetch_contract_code import FetchContractCodeTool


def initialize_tools(account_index: str = "0"):
    """
    Initialize and return a dictionary of available tools.
    """
    # this will be exposed by an endpoint for the frontend to get the available tools
    return {
        "alex_get_price_history": AlexGetPriceHistory(),
        "alex_get_swap_info": AlexGetSwapInfo(),
        "alex_get_token_pool_volume": AlexGetTokenPoolVolume(),
        "bitflow_get_available_tokens": BitflowGetAvailableTokens(),
        "bitflow_execute_trade": BitflowExecuteTradeTool(account_index),
        "lunarcrush_get_token_data": LunarCrushTokenMetricsTool(),
        "lunarcrush_search": SearchLunarCrushTool(),
        "lunarcrush_get_token_metadata": LunarCrushTokenMetadataTool(),
        "web_search_experimental": SerperDevTool(),
        "velar_get_token_price_history": VelarGetPriceHistory(),
        "velar_get_tokens": VelarGetTokens(),
        "wallet_get_my_balance": WalletGetMyBalance(account_index),
        "wallet_get_my_address": WalletGetMyAddress(account_index),
        "stacks_transaction_status": StacksTransactionStatusTool(),
        "stacks_transaction": StacksTransactionTool(),
        "stacks_transaction_by_address": StacksTransactionByAddressTool(),
    }


def get_agent_tools(tool_names, tools_map):
    """
    Get the tools for an agent based on the tool names.

    Args:
        tool_names (list): List of tool names for the agent.
        tools_map (dict): Dictionary mapping tool names to tool instances.

    Returns:
        list: List of tool instances for the agent.
    """
    return [tools_map[name] for name in tool_names if name in tools_map]
