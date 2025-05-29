# tool imports
from typing import Dict, List, Optional

from langchain.tools.base import BaseTool as LangChainBaseTool

from backend.factory import backend
from backend.models import UUID, Profile, WalletFilter
from lib.logger import configure_logger

from .agent_account import AgentAccountDeployTool
from .bitflow import BitflowExecuteTradeTool
from .coinmarketcap import GetBitcoinData
from .contracts import ContractSIP10InfoTool, FetchContractSourceTool
from .dao_deployments import ContractDAODeployTool
from .dao_ext_action_proposals import (
    ConcludeActionProposalTool,
    GetLiquidSupplyTool,
    GetProposalTool,
    GetTotalVotesTool,
    GetVotingConfigurationTool,
    GetVotingPowerTool,
    ProposeActionSendMessageTool,
    VoteOnActionProposalTool,
)
from .dao_ext_charter import (
    GetCurrentDaoCharterTool,
    GetCurrentDaoCharterVersionTool,
    GetDaoCharterTool,
)
from .dao_ext_treasury import GetAllowedAssetTool, IsAllowedAssetTool
from .database import (
    AddScheduledTaskTool,
    DeleteScheduledTaskTool,
    GetDAOByNameTool,
    GetDAOListTool,
    ListScheduledTasksTool,
    UpdateScheduledTaskTool,
)
from .faktory import (
    FaktoryExecuteBuyStxTool,
    FaktoryExecuteBuyTool,
    FaktoryExecuteSellTool,
    FaktoryGetSbtcTool,
)
from .hiro import STXGetContractInfoTool, STXGetPrincipalAddressBalanceTool
from .lunarcrush import (
    LunarCrushTokenMetadataTool,
    LunarCrushTokenMetricsTool,
    SearchLunarCrushTool,
)
from .telegram import SendTelegramNotificationTool
from .transactions import (
    StacksTransactionByAddressTool,
    StacksTransactionTool,
)
from .twitter import TwitterPostTweetTool
from .wallet import (
    WalletFundMyWalletFaucet,
    WalletGetMyAddress,
    WalletGetMyBalance,
    WalletGetMyTransactions,
    WalletSendSTX,
    WalletSIP10SendTool,
)
from .x_credentials import CollectXCredentialsTool

logger = configure_logger(__name__)


def initialize_tools(
    profile: Optional[Profile] = None,
    agent_id: Optional[UUID] = None,
) -> Dict[str, LangChainBaseTool]:
    """Initialize and return a dictionary of available LangChain tools.

    Args:
        profile: The user profile, can be None
        agent_id: The ID of the agent to initialize tools for, can be None

    Returns:
        Dictionary of initialized tools
    """

    wallet_id = None
    profile_id = profile.id if profile else None
    if profile:
        if not agent_id:
            try:
                wallet = backend.list_wallets(
                    filters=WalletFilter(profile_id=profile_id)
                )[0]
                wallet_id = wallet.id
            except (IndexError, Exception) as e:
                logger.warning(f"Failed to get wallet for profile {profile_id}: {e}")
        else:
            # Get the wallet associated with this agent
            try:
                wallet = backend.list_wallets(
                    filters=WalletFilter(profile_id=profile_id, agent_id=agent_id)
                )[0]
                wallet_id = wallet.id
            except Exception as e:
                logger.warning(f"Failed to get wallet for agent {agent_id}: {e}")

    tools = {
        "bitflow_execute_trade": BitflowExecuteTradeTool(wallet_id),
        "contracts_fetch_source_code": FetchContractSourceTool(wallet_id),
        "database_add_scheduled_task": AddScheduledTaskTool(profile_id, agent_id),
        "database_get_dao_list": GetDAOListTool(),
        "database_get_dao_get_by_name": GetDAOByNameTool(),
        "database_list_scheduled_tasks": ListScheduledTasksTool(profile_id, agent_id),
        "database_update_scheduled_task": UpdateScheduledTaskTool(profile_id, agent_id),
        "database_delete_scheduled_task": DeleteScheduledTaskTool(profile_id, agent_id),
        "faktory_get_sbtc": FaktoryGetSbtcTool(wallet_id),
        "faktory_exec_buy": FaktoryExecuteBuyTool(wallet_id),
        "faktory_exec_buy_stx": FaktoryExecuteBuyStxTool(wallet_id),
        "faktory_exec_sell": FaktoryExecuteSellTool(wallet_id),
        "lunarcrush_get_token_metrics": LunarCrushTokenMetricsTool(),
        "lunarcrush_search": SearchLunarCrushTool(),
        "lunarcrush_get_token_metadata": LunarCrushTokenMetadataTool(),
        "stacks_get_transaction_details": StacksTransactionTool(wallet_id),
        "stacks_get_transactions_by_address": StacksTransactionByAddressTool(wallet_id),
        "stacks_get_contract_info": STXGetContractInfoTool(),
        "stacks_get_address_balance": STXGetPrincipalAddressBalanceTool(),
        "telegram_send_nofication_to_user": SendTelegramNotificationTool(profile_id),
        "twitter_post_tweet": TwitterPostTweetTool(agent_id),
        "wallet_get_my_balance": WalletGetMyBalance(wallet_id),
        "wallet_get_my_address": WalletGetMyAddress(wallet_id),
        "wallet_fund_my_wallet_faucet": WalletFundMyWalletFaucet(wallet_id),
        "wallet_send_stx": WalletSendSTX(wallet_id),
        "wallet_get_my_transactions": WalletGetMyTransactions(wallet_id),
        "wallet_send_sip10": WalletSIP10SendTool(wallet_id),
        "x_credentials": CollectXCredentialsTool(profile_id),
        "agent_account_deploy": AgentAccountDeployTool(wallet_id),
    }

    return tools


def filter_tools_by_names(
    tool_names: List[str], tools_map: Dict[str, LangChainBaseTool]
) -> Dict[str, LangChainBaseTool]:
    """Get LangChain tools for an agent based on the tool names."""
    return {name: tool for name, tool in tools_map.items() if name in tool_names}


def exclude_tools_by_names(
    tool_names: List[str], tools_map: Dict[str, LangChainBaseTool]
) -> Dict[str, LangChainBaseTool]:
    """Get LangChain tools for an agent by excluding specified tool names.

    Args:
        tool_names: List of tool names to exclude
        tools_map: Dictionary of all available tools

    Returns:
        Dictionary of tools with specified names excluded
    """
    return {name: tool for name, tool in tools_map.items() if name not in tool_names}
