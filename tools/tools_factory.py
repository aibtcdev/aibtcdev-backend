# from .get_btc_data import GetBitcoinData
from crewai_tools import SerperDevTool
from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowGetAvailableTokens, BitflowExecuteTradeTool
from .lunarcrush import LunarCrushGetTokenData, LunarCrushSearch


# from .fetch_contract_code import FetchContractCodeTool


def initialize_tools(account_index: str = "0"):
    """
    Initialize and return a dictionary of available tools.
    """
    # NAMES SHOULD BE EXACTLY WHAT'S IN THE FRONTEND
    print(
        f"Initializing BitflowExecuteTradeTool with account_index: {account_index}"
    )  # Debugging line
    return {
        "alex_get_price_history": AlexGetPriceHistory(),
        "alex_get_swap_info": AlexGetSwapInfo(),
        "alex_get_token_pool_volume": AlexGetTokenPoolVolume(),
        "bitflow_get_available_tokens": BitflowGetAvailableTokens(),
        "bitflow_execute_trade": BitflowExecuteTradeTool(account_index),
        "lunarcrush_get_token_data": LunarCrushGetTokenData(),
        "lunarcrush_search": LunarCrushSearch(),
        "web_search_experimental": SerperDevTool(),
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
