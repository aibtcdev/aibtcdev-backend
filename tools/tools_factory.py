import inspect
from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowExecuteTradeTool, BitflowGetAvailableTokens
from .contracts import ContractSIP10InfoTool, FetchContractSourceTool
from .dao import (
    ActionConcludeProposalTool,
    ActionGetLinkedVotingContractsTool,
    ActionGetProposalTool,
    ActionGetTotalProposalsTool,
    ActionGetTotalVotesTool,
    ActionGetVotingPowerTool,
    ActionVoteOnProposalTool,
    BuyTokenTool,
    CoreConcludeProposalTool,
    CoreCreateProposalTool,
    CoreGetLinkedVotingContractsTool,
    CoreGetProposalTool,
    CoreGetTotalVotesTool,
    CoreGetVotingPowerTool,
    CoreVoteOnProposalTool,
    ProposeActionAddResourceTool,
    ProposeActionAllowAssetTool,
    ProposeActionSendMessageTool,
    ProposeActionSetAccountHolderTool,
    ProposeActionSetWithdrawalAmountTool,
    ProposeActionSetWithdrawalPeriodTool,
    ProposeActionToggleResourceTool,
    SellTokenTool,
)
from .daos import ContractDAODeployTool
from .db import (
    AddScheduledTaskTool,
    DeleteScheduledTaskTool,
    GetDAOByNameTool,
    GetDAOListTool,
    ListScheduledTasksTool,
    UpdateScheduledTaskTool,
)
from .faktory import (
    FaktoryExecuteBuyTool,
    FaktoryExecuteSellTool,
    FaktoryGetBuyQuoteTool,
    FaktoryGetDaoTokensTool,
    FaktoryGetSellQuoteTool,
    FaktoryGetTokenTool,
)
from .get_btc_data import GetBitcoinData
from .hiro import (
    STXGetContractInfoTool,
    STXGetPrincipalAddressBalanceTool,
    STXPriceTool,
)
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
    StxCityExecuteBuyTool,
    StxCityExecuteSellTool,
    StxCityListBondingTokensTool,
    StxCitySearchTool,
)
from .telegram import SendTelegramNotificationTool
from .transactions import (
    StacksTransactionByAddressTool,
    StacksTransactionStatusTool,
    StacksTransactionTool,
)
from .twitter import TwitterPostTweetTool
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
from backend.models import UUID, Profile, WalletFilter
from langchain.tools.base import BaseTool as LangChainBaseTool
from lib.logger import configure_logger
from pydantic import BaseModel, ConfigDict, create_model
from typing import Any, Callable, Dict, List, Optional, Type

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
        "alex_get_price_history": AlexGetPriceHistory(),
        "alex_get_swap_info": AlexGetSwapInfo(),
        "alex_get_token_pool_volume": AlexGetTokenPoolVolume(),
        "bitflow_available_tokens": BitflowGetAvailableTokens(wallet_id),
        "bitflow_execute_trade": BitflowExecuteTradeTool(wallet_id),
        "lunarcrush_get_token_data": LunarCrushTokenMetricsTool(),
        "lunarcrush_search": SearchLunarCrushTool(),
        "lunarcrush_get_token_metadata": LunarCrushTokenMetadataTool(),
        "db_add_scheduled_task": AddScheduledTaskTool(profile_id, agent_id),
        "dao_list": GetDAOListTool(),
        "dao_get_by_name": GetDAOByNameTool(),
        "db_list_scheduled_tasks": ListScheduledTasksTool(profile_id, agent_id),
        "db_update_scheduled_task": UpdateScheduledTaskTool(profile_id, agent_id),
        "db_delete_scheduled_task": DeleteScheduledTaskTool(profile_id, agent_id),
        "faktory_exec_buy": FaktoryExecuteBuyTool(wallet_id),
        "faktory_exec_sell": FaktoryExecuteSellTool(wallet_id),
        "faktory_get_buy_quote": FaktoryGetBuyQuoteTool(wallet_id),
        "faktory_get_dao_tokens": FaktoryGetDaoTokensTool(wallet_id),
        "faktory_get_sell_quote": FaktoryGetSellQuoteTool(wallet_id),
        "faktory_get_token": FaktoryGetTokenTool(wallet_id),
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
        "stacks_get_contract_info": STXGetContractInfoTool(),
        "stacks_get_principal_address_balance": STXGetPrincipalAddressBalanceTool(),
        "contract_sip10_info": ContractSIP10InfoTool(wallet_id),
        "contract_dao_deploy": ContractDAODeployTool(wallet_id),
        "contract_source_fetch": FetchContractSourceTool(wallet_id),
        "btc_price": GetBitcoinData(),
        #"stxcity_search": StxCitySearchTool(wallet_id),
        #"stxcity_execute_sell": StxCityExecuteSellTool(wallet_id),
        #"stxcity_execute_buy": StxCityExecuteBuyTool(wallet_id),
        #"stxcity_list_bonding_tokens": StxCityListBondingTokensTool(wallet_id),
        "twitter_post_tweet": TwitterPostTweetTool(agent_id),
        "dao_core_get_linked_voting_contracts": CoreGetLinkedVotingContractsTool(
            wallet_id
        ),
        #"dao_core_create_proposal": CoreCreateProposalTool(wallet_id),
        #"dao_core_get_proposal": CoreGetProposalTool(wallet_id),
        #"dao_core_get_total_votes": CoreGetTotalVotesTool(wallet_id),
        #"dao_core_get_voting_power": CoreGetVotingPowerTool(wallet_id),
        #"dao_core_vote_on_proposal": CoreVoteOnProposalTool(wallet_id),
        #"dao_core_conclude_proposal": CoreConcludeProposalTool(wallet_id),
        #"dao_action_get_linked_voting_contracts": ActionGetLinkedVotingContractsTool(
        #    wallet_id
        #),
        #"dao_action_get_proposal": ActionGetProposalTool(wallet_id),
        #"dao_action_get_total_votes": ActionGetTotalVotesTool(wallet_id),
        #"dao_action_get_voting_power": ActionGetVotingPowerTool(wallet_id),
        #"dao_action_vote_on_proposal": ActionVoteOnProposalTool(wallet_id),
        #"dao_action_conclude_proposal": ActionConcludeProposalTool(wallet_id),
        #"dao_action_get_total_proposals": ActionGetTotalProposalsTool(wallet_id),
        #"dao_buy_token": BuyTokenTool(wallet_id),
        #"dao_sell_token": SellTokenTool(wallet_id),
        #"dao_propose_action_add_resource": ProposeActionAddResourceTool(wallet_id),
        #"dao_propose_action_allow_asset": ProposeActionAllowAssetTool(wallet_id),
        #"dao_propose_action_send_message": ProposeActionSendMessageTool(wallet_id),
        #"dao_propose_action_set_account_holder": ProposeActionSetAccountHolderTool(
        #    wallet_id
        #),
        #"dao_propose_action_set_withdrawal_amount": ProposeActionSetWithdrawalAmountTool(
        #    wallet_id
        #),
        #"dao_propose_action_set_withdrawal_period": ProposeActionSetWithdrawalPeriodTool(
        #    wallet_id
        #),
        #"dao_propose_action_toggle_resource": ProposeActionToggleResourceTool(
        #    wallet_id
        #),
        "telegram_nofication_to_user": SendTelegramNotificationTool(profile_id),
    }

    return tools


def filter_tools_by_names(
    tool_names: List[str], tools_map: Dict[str, LangChainBaseTool]
) -> Dict[str, LangChainBaseTool]:
    """Get LangChain tools for an agent based on the tool names."""
    return {name: tool for name, tool in tools_map.items() if name in tool_names}
