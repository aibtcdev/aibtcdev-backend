from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowExecuteTradeTool, BitflowGetAvailableTokens
from .contracts import (
    ContractSIP10DeployTool,
    ContractSIP10InfoTool,
    ContractSIP10SendTool,
)
from .fetch_contract_code import FetchContractCodeTool
from .get_btc_data import GetBitcoinData
from .lunarcrush import (
    LunarCrushTokenMetadataTool,
    LunarCrushTokenMetricsTool,
    SearchLunarCrushTool,
)
from .stxcity import STXCityBondingTool
from .transactions import (
    StacksTransactionByAddressTool,
    StacksTransactionStatusTool,
    StacksTransactionTool,
)
from .velar import VelarGetPriceHistory, VelarGetTokens
from .wallet import WalletGetMyAddress, WalletGetMyBalance, WalletSendSTX
from crewai_tools import DallETool, SerperDevTool


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
        "wallet_send_stx": WalletSendSTX(account_index),
        "stacks_transaction_status": StacksTransactionStatusTool(),
        "stacks_transaction": StacksTransactionTool(),
        "stacks_transaction_by_address": StacksTransactionByAddressTool(),
        "contract_sip10_deploy": ContractSIP10DeployTool(account_index),
        "contract_sip10_send": ContractSIP10SendTool(account_index),
        "contract_sip10_info": ContractSIP10InfoTool(account_index),
        "fetch_contract_code": FetchContractCodeTool(),
        "get_btc_data": GetBitcoinData(),
        "image_generation": DallETool(),
        "deploy_bonding_curve": STXCityBondingTool(account_index),
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
