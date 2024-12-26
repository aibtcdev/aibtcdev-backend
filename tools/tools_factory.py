from crewai_tools import SerperDevTool
from .get_btc_data import GetBitcoinData
from .velar import VelarGetPriceHistory, VelarGetTokens
from .wallet import WalletGetMyAddress, WalletGetMyBalance, WalletSendSTX
from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowGetAvailableTokens, BitflowExecuteTradeTool
from .fetch_contract_code import FetchContractCodeTool
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
from .contracts import ContractSIP10DeployTool, ContractSIP10SendTool, ContractSIP10InfoTool
from .dao import (
    ExecutorListTool,
    ExecutorDeployTool,
    ExecutorSetExtensionTool,
    TreasuryListTool,
    TreasuryDeployTool,
    TreasuryDepositTool,
    TreasuryWithdrawTool
)


def initialize_tools(account_index: str = "0"):
    """
    Initialize and return a dictionary of available tools.
    
    Args:
        account_index (str): The account index to use for tools that require it.
        
    Returns:
        dict: A dictionary mapping tool names to tool instances.
    """
    return {
        # Existing tools
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
        
        # DAO Executor tools
        "dao_executor_list": ExecutorListTool(account_index),
        "dao_executor_deploy": ExecutorDeployTool(account_index),
        "dao_executor_set_extension": ExecutorSetExtensionTool(account_index),
        
        # DAO Treasury tools
        "dao_treasury_list": TreasuryListTool(account_index),
        "dao_treasury_deploy": TreasuryDeployTool(account_index),
        "dao_treasury_deposit": TreasuryDepositTool(account_index),
        "dao_treasury_withdraw": TreasuryWithdrawTool(account_index),
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