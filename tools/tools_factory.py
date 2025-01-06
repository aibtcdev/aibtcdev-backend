from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowExecuteTradeTool, BitflowGetAvailableTokens
from .collectives import ContractCollectiveDeployTool
from .contracts import (
    ContractSIP10DeployTool,
    ContractSIP10InfoTool,
    FetchContractSourceTool,
)
from .db import AddScheduledTaskTool, GetCollectiveListTool
from .get_btc_data import GetBitcoinData
from .hiro import STXPriceTool
from .jing import (
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
from .lunarcrush import (
    LunarCrushTokenMetadataTool,
    LunarCrushTokenMetricsTool,
    SearchLunarCrushTool,
)
from .stxcity import (
    StxCityCheckValidBondingTool,
    StxCityExecuteBuyTool,
    StxCityExecuteSellTool,
    StxCityListBondingTokensTool,
    StxCitySearchTool,
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
from backend.factory import backend
from backend.models import Profile, WalletFilter
from crewai_tools import BaseTool as CrewAIBaseTool
from langchain.tools.base import BaseTool as LangChainBaseTool
from lib.logger import configure_logger
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = configure_logger(__name__)


def initialize_tools(
    profile: Profile,
    agent_id: UUID,
    wallet_id: Optional[UUID] = None,
    crewai: bool = True,
) -> Dict[str, LangChainBaseTool | CrewAIBaseTool]:
    """Initialize and return a dictionary of available LangChain tools.

    Args:
        profile: The user profile
        agent_id: The ID of the agent to initialize tools for
        wallet_id: Optional wallet ID to use instead of looking up from backend
        crewai: Whether to use CrewAI tools

    Returns:
        Dictionary of initialized tools
    """
    if not wallet_id:
        # Get the wallet associated with this agent
        try:
            wallet = backend.list_wallets(
                filters=WalletFilter(profile_id=profile.id, agent_id=agent_id)
            )[0]
            if not wallet:
                raise ValueError(f"No wallet found for agent {agent_id}")
            wallet_id = wallet.id
        except Exception as e:
            logger.warning(f"Failed to get wallet for agent {agent_id}: {e}")
            wallet_id = UUID("00000000-0000-0000-0000-000000000000")

    tools = {
        "alex_get_price_history": AlexGetPriceHistory(),
        "alex_get_swap_info": AlexGetSwapInfo(),
        "alex_get_token_pool_volume": AlexGetTokenPoolVolume(),
        "bitflow_available_tokens": BitflowGetAvailableTokens(wallet_id),
        "bitflow_execute_trade": BitflowExecuteTradeTool(wallet_id),
        "lunarcrush_get_token_data": LunarCrushTokenMetricsTool(),
        "lunarcrush_search": SearchLunarCrushTool(),
        "lunarcrush_get_token_metadata": LunarCrushTokenMetadataTool(),
        "db_add_scheduled_task": AddScheduledTaskTool(profile.id, agent_id),
        "db_list_collectives_daos": GetCollectiveListTool(),
        "jing_get_order_book": JingGetOrderBookTool(wallet_id),
        "jing_create_bid": JingCreateBidTool(wallet_id),
        "jing_cancel_ask": JingCancelAskTool(wallet_id),
        "jing_cancel_bid": JingCancelBidTool(wallet_id),
        "jing_get_ask": JingGetAskTool(wallet_id),
        "jing_get_bid": JingGetBidTool(wallet_id),
        "jing_get_markets": JingGetMarketsTool(wallet_id),
        "jing_get_pending_orders": JingGetPendingOrdersTool(wallet_id),
        "jing_submit_ask": JingSubmitAskTool(wallet_id),
        "jing_submit_bid": JingSubmitBidTool(wallet_id),
        "velar_get_token_price_history": VelarGetPriceHistory(),
        "velar_get_tokens": VelarGetTokens(),
        "wallet_get_my_balance": WalletGetMyBalance(wallet_id),
        "wallet_get_my_address": WalletGetMyAddress(wallet_id),
        "wallet_fund_my_wallet_faucet": WalletFundMyWalletFaucet(wallet_id),
        "wallet_send_stx": WalletSendSTX(wallet_id),
        "wallet_get_my_transactions": WalletGetMyTransactions(wallet_id),
        "wallet_sip10_send": WalletSIP10SendTool(wallet_id),
        "stacks_transaction_status": StacksTransactionStatusTool(wallet_id),
        "stacks_transaction": StacksTransactionTool(wallet_id),
        "stacks_transaction_by_address": StacksTransactionByAddressTool(wallet_id),
        "stacks_stx_price": STXPriceTool(),
        # "contract_sip10_deploy": ContractSIP10DeployTool(wallet_id),
        # "contract_dao_executor_deploy": ContractDAOExecutorDeployTool(wallet_id),
        "contract_sip10_info": ContractSIP10InfoTool(wallet_id),
        "contract_collective_deploy": ContractCollectiveDeployTool(wallet_id),
        "contract_source_fetch": FetchContractSourceTool(wallet_id),
        "btc_price": GetBitcoinData(),
        "stxcity_search": StxCitySearchTool(wallet_id),
        "stxcity_execute_sell": StxCityExecuteSellTool(wallet_id),
        "stxcity_execute_buy": StxCityExecuteBuyTool(wallet_id),
        "stxcity_check_valid_bonding": StxCityCheckValidBondingTool(wallet_id),
        "stxcity_list_bonding_tokens": StxCityListBondingTokensTool(wallet_id),
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
