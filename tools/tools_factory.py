from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowExecuteTradeTool, BitflowGetAvailableTokens
from .contracts import (
    ContractSIP10DeployTool,
    ContractSIP10InfoTool,
    FetchContractSourceTool,
)
from .get_btc_data import GetBitcoinData
from .lunarcrush import (
    LunarCrushTokenMetadataTool,
    LunarCrushTokenMetricsTool,
    SearchLunarCrushTool,
)
from .transactions import (
    StacksTransactionByAddressTool,
    StacksTransactionStatusTool,
    StacksTransactionTool,
)
from .velar import VelarGetPriceHistory, VelarGetTokens
from .wallet import (
    WalletFundMyWalletFaucet,
    WalletGetMyAddress,
    WalletGetMyBalance,
    WalletGetMyTransactions,
    WalletSendSTX,
    WalletSIP10SendTool,
)
from backend.models import Profile
from crewai_tools import BaseTool as CrewAIBaseTool
from langchain.tools.base import BaseTool as LangChainBaseTool
from lib.logger import configure_logger
from tools.collectives import ContractCollectiveDeployTool
from tools.db import AddScheduledTaskTool
from tools.hiro import STXPriceTool
from tools.jing import (
    JingCancelAskTool,
    JingCancelBidTool,
    JingCreateBidTool,
    JingGetAskTool,
    JingGetBidTool,
    JingGetMarketsTool,
    JingGetOrderBookTool,
    JingGetPendingOrdersTool,
    JingSubmitAskTool,
    JingSubmitBidTool,
)
from tools.stxcity import (
    StxCityCheckValidBondingTool,
    StxCityExecuteBuyTool,
    StxCityExecuteSellTool,
    StxCityListBondingTokensTool,
    StxCitySearchTool,
)
from typing import Any, Dict, List, Optional

logger = configure_logger(__name__)


def initialize_tools(
    profile: Profile,
    agent_id: str = "e8325a19-633b-466c-b4c1-19c37a084778",
    crewai: bool = True,
) -> Dict[str, LangChainBaseTool | CrewAIBaseTool]:
    """Initialize and return a dictionary of available LangChain tools."""
    # Convert account_index to string
    account_index = (
        str(profile.account_index) if profile.account_index is not None else "0"
    )

    tools = {
        "alex_get_price_history": AlexGetPriceHistory(),
        "alex_get_swap_info": AlexGetSwapInfo(),
        "alex_get_token_pool_volume": AlexGetTokenPoolVolume(),
        "bitflow_available_tokens": BitflowGetAvailableTokens(),
        "bitflow_execute_trade": BitflowExecuteTradeTool(account_index),
        "lunarcrush_get_token_data": LunarCrushTokenMetricsTool(),
        "lunarcrush_search": SearchLunarCrushTool(),
        "lunarcrush_get_token_metadata": LunarCrushTokenMetadataTool(),
        "db_add_scheduled_task": AddScheduledTaskTool(profile.id, agent_id),
        "jing_get_order_book": JingGetOrderBookTool(account_index),
        "jing_create_bid": JingCreateBidTool(account_index),
        "jing_cancel_ask": JingCancelAskTool(account_index),
        "jing_cancel_bid": JingCancelBidTool(account_index),
        "jing_get_ask": JingGetAskTool(account_index),
        "jing_get_bid": JingGetBidTool(account_index),
        "jing_get_markets": JingGetMarketsTool(account_index),
        "jing_get_pending_orders": JingGetPendingOrdersTool(account_index),
        "jing_submit_ask": JingSubmitAskTool(account_index),
        "jing_submit_bid": JingSubmitBidTool(account_index),
        "velar_get_token_price_history": VelarGetPriceHistory(),
        "velar_get_tokens": VelarGetTokens(),
        "wallet_get_my_balance": WalletGetMyBalance(account_index),
        "wallet_get_my_address": WalletGetMyAddress(account_index),
        "wallet_fund_my_wallet_faucet": WalletFundMyWalletFaucet(account_index),
        "wallet_send_stx": WalletSendSTX(account_index),
        "wallet_get_my_transactions": WalletGetMyTransactions(account_index),
        "wallet_sip10_send": WalletSIP10SendTool(account_index),
        "stacks_transaction_status": StacksTransactionStatusTool(),
        "stacks_transaction": StacksTransactionTool(),
        "stacks_transaction_by_address": StacksTransactionByAddressTool(),
        "stacks_stx_price": STXPriceTool(),
        # "contract_sip10_deploy": ContractSIP10DeployTool(account_index),
        # "contract_dao_executor_deploy": ContractDAOExecutorDeployTool(account_index),
        "contract_sip10_info": ContractSIP10InfoTool(account_index),
        "contract_collective_deploy": ContractCollectiveDeployTool(account_index),
        "contract_source_fetch": FetchContractSourceTool(),
        "btc_price": GetBitcoinData(),
        "stxcity_search": StxCitySearchTool(account_index),
        "stxcity_execute_sell": StxCityExecuteSellTool(account_index),
        "stxcity_execute_buy": StxCityExecuteBuyTool(account_index),
        "stxcity_check_valid_bonding": StxCityCheckValidBondingTool(account_index),
        "stxcity_list_bonding_tokens": StxCityListBondingTokensTool(account_index),
    }

    if crewai:
        logger.info("Adding CrewAI tools")
        tools.update(get_crewai_tools_map(tools))

    return tools


def filter_tools_by_names(
    tool_names: List[str], tools_map: Dict[str, LangChainBaseTool]
) -> Dict[str, LangChainBaseTool]:
    """Get LangChain tools for an agent based on the tool names."""
    return {name: tool for name, tool in tools_map.items() if name in tool_names}


def filter_crewai_tools_by_names(
    tool_names: List[str], tools_map: Dict[str, CrewAIBaseTool]
) -> Dict[str, CrewAIBaseTool]:
    """Get CrewAI tools for an agent based on the tool names."""
    return {name: tool for name, tool in tools_map.items() if name in tool_names}


def get_crewai_tools_map(
    tools_map: Dict[str, LangChainBaseTool]
) -> Dict[str, CrewAIBaseTool]:
    """Get map of tools in CrewAI format."""
    return {name: convert_langchain_to_crewai(tool) for name, tool in tools_map.items()}


def convert_langchain_to_crewai(langchain_tool: LangChainBaseTool) -> CrewAIBaseTool:
    """Convert a LangChain tool into a CrewAI tool."""

    class CrewAIToolWrapper(CrewAIBaseTool):
        name: str = langchain_tool.name
        description: str = langchain_tool.description
        args_schema = langchain_tool.args_schema
        return_direct: bool = getattr(langchain_tool, "return_direct", True)

        def __init__(self):
            super().__init__()
            # Copy any additional attributes from the langchain tool
            for attr in dir(langchain_tool):
                if not attr.startswith("_") and not hasattr(self, attr):
                    setattr(self, attr, getattr(langchain_tool, attr))

        def _run(self, *args: Any, **kwargs: Any) -> Any:
            return langchain_tool._run(*args, **kwargs)

        async def _arun(self, *args: Any, **kwargs: Any) -> Any:
            if hasattr(langchain_tool, "_arun"):
                return await langchain_tool._arun(*args, **kwargs)
            return await super()._arun(*args, **kwargs)

    return CrewAIToolWrapper()
