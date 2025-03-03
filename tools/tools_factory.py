import inspect
from typing import Any, Callable, Dict, List, Optional, Type

from langchain.tools.base import BaseTool as LangChainBaseTool
from pydantic import BaseModel, ConfigDict, create_model

from backend.factory import backend
from backend.models import UUID, Profile, WalletFilter
from lib.logger import configure_logger

# tool imports
from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowExecuteTradeTool, BitflowGetAvailableTokens
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
    ProposeActionAddResourceTool,
    ProposeActionAllowAssetTool,
    ProposeActionSendMessageTool,
    ProposeActionSetAccountHolderTool,
    ProposeActionSetWithdrawalAmountTool,
    ProposeActionSetWithdrawalPeriodTool,
    ProposeActionToggleResourceTool,
    VoteOnActionProposalTool,
)
from .dao_ext_bank_account import DepositSTXTool, GetAccountTermsTool, WithdrawSTXTool
from .dao_ext_charter import (
    GetCurrentDaoCharterTool,
    GetCurrentDaoCharterVersionTool,
    GetDaoCharterTool,
)
from .dao_ext_onchain_messaging import SendMessageTool
from .dao_ext_payments_invoices import (
    GetInvoiceTool,
    GetResourceByNameTool,
    GetResourceTool,
    PayInvoiceByResourceNameTool,
    PayInvoiceTool,
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
    FaktoryGetSbtcTool,
    FaktoryExecuteBuyTool,
    FaktoryExecuteSellTool,
    FaktoryGetBuyQuoteTool,
    FaktoryGetDaoTokensTool,
    FaktoryGetSellQuoteTool,
    FaktoryGetTokenTool,
)
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
        # "alex_get_price_history": AlexGetPriceHistory(),
        # "alex_get_swap_info": AlexGetSwapInfo(),
        # "alex_get_token_pool_volume": AlexGetTokenPoolVolume(),
        "coinmarketcap_get_market_data": GetBitcoinData(),
        # "bitflow_get_available_tokens": BitflowGetAvailableTokens(wallet_id),
        "bitflow_execute_trade": BitflowExecuteTradeTool(wallet_id),
        "contracts_get_sip10_info": ContractSIP10InfoTool(wallet_id),
        "contracts_deploy_dao": ContractDAODeployTool(wallet_id),
        "contracts_fetch_source_code": FetchContractSourceTool(wallet_id),
        "dao_actionproposals_conclude_proposal": ConcludeActionProposalTool(wallet_id),
        "dao_actionproposals_get_liquid_supply": GetLiquidSupplyTool(wallet_id),
        "dao_actionproposals_get_proposal": GetProposalTool(wallet_id),
        "dao_actionproposals_get_total_votes": GetTotalVotesTool(wallet_id),
        "dao_actionproposals_get_voting_configuration": GetVotingConfigurationTool(
            wallet_id
        ),
        "dao_actionproposals_get_voting_power": GetVotingPowerTool(wallet_id),
        "dao_actionproposals_vote_on_proposal": VoteOnActionProposalTool(wallet_id),
        "dao_actionproposals_propose_add_resource": ProposeActionAddResourceTool(
            wallet_id
        ),
        "dao_actionproposals_propose_allow_asset": ProposeActionAllowAssetTool(
            wallet_id
        ),
        "dao_actionproposals_propose_send_message": ProposeActionSendMessageTool(
            wallet_id
        ),
        "dao_actionproposals_propose_set_account_holder": ProposeActionSetAccountHolderTool(
            wallet_id
        ),
        "dao_actionproposals_propose_set_withdrawal_amount": ProposeActionSetWithdrawalAmountTool(
            wallet_id
        ),
        "dao_actionproposals_propose_set_withdrawal_period": ProposeActionSetWithdrawalPeriodTool(
            wallet_id
        ),
        "dao_actionproposals_propose_toggle_resource": ProposeActionToggleResourceTool(
            wallet_id
        ),
        "dao_bank_get_account_terms": GetAccountTermsTool(wallet_id),
        "dao_bank_deposit_stx": DepositSTXTool(wallet_id),
        "dao_bank_withdraw_stx": WithdrawSTXTool(wallet_id),
        "dao_charter_get_current": GetCurrentDaoCharterTool(wallet_id),
        "dao_charter_get_current_version": GetCurrentDaoCharterVersionTool(wallet_id),
        "dao_charter_get_version": GetDaoCharterTool(wallet_id),
        "dao_messaging_send": SendMessageTool(wallet_id),
        "dao_payments_get_invoice": GetInvoiceTool(wallet_id),
        "dao_payments_get_resource": GetResourceTool(wallet_id),
        "dao_payments_get_resource_by_name": GetResourceByNameTool(wallet_id),
        "dao_payments_pay_invoice": PayInvoiceTool(wallet_id),
        "dao_payments_pay_invoice_by_resource": PayInvoiceByResourceNameTool(wallet_id),
        "dao_treasury_get_allowed_asset": GetAllowedAssetTool(wallet_id),
        "dao_treasury_is_allowed_asset": IsAllowedAssetTool(wallet_id),
        "database_add_scheduled_task": AddScheduledTaskTool(profile_id, agent_id),
        "database_get_dao_list": GetDAOListTool(),
        "database_get_dao_get_by_name": GetDAOByNameTool(),
        "database_list_scheduled_tasks": ListScheduledTasksTool(profile_id, agent_id),
        "database_update_scheduled_task": UpdateScheduledTaskTool(profile_id, agent_id),
        "database_delete_scheduled_task": DeleteScheduledTaskTool(profile_id, agent_id),
        "faktory_get_sbtc": FaktoryGetSbtcTool(),
        "faktory_exec_buy": FaktoryExecuteBuyTool(wallet_id),
        "faktory_exec_sell": FaktoryExecuteSellTool(wallet_id),
        # "faktory_get_buy_quote": FaktoryGetBuyQuoteTool(wallet_id),
        # "faktory_get_dao_tokens": FaktoryGetDaoTokensTool(wallet_id),
        # "faktory_get_sell_quote": FaktoryGetSellQuoteTool(wallet_id),
        # "faktory_get_token": FaktoryGetTokenTool(wallet_id),
        # "jing_get_order_book": JingGetOrderBookTool(wallet_id),
        # "jing_create_bid": JingCreateBidTool(wallet_id),
        # "jing_cancel_ask": JingCancelAskTool(wallet_id),
        # "jing_cancel_bid": JingCancelBidTool(wallet_id),
        # "jing_get_ask": JingGetAskTool(wallet_id),
        # "jing_get_bid": JingGetBidTool(wallet_id),
        # "jing_get_markets": JingGetMarketsTool(wallet_id),
        # "jing_get_pending_orders": JingGetPendingOrdersTool(wallet_id),
        # "jing_submit_ask": JingSubmitAskTool(wallet_id),
        # "jing_submit_bid": JingSubmitBidTool(wallet_id),
        "lunarcrush_get_token_metrics": LunarCrushTokenMetricsTool(),
        "lunarcrush_search": SearchLunarCrushTool(),
        "lunarcrush_get_token_metadata": LunarCrushTokenMetadataTool(),
        "stacks_get_transaction_status": StacksTransactionStatusTool(wallet_id),
        "stacks_get_transaction_details": StacksTransactionTool(wallet_id),
        "stacks_get_transactions_by_address": StacksTransactionByAddressTool(wallet_id),
        # "stacks_get_stx_price": STXPriceTool(),
        "stacks_get_contract_info": STXGetContractInfoTool(),
        "stacks_get_address_balance": STXGetPrincipalAddressBalanceTool(),
        "telegram_send_nofication_to_user": SendTelegramNotificationTool(profile_id),
        "twitter_post_tweet": TwitterPostTweetTool(agent_id),
        "velar_get_token_price_history": VelarGetPriceHistory(),
        "velar_get_tokens": VelarGetTokens(),
        "wallet_get_my_balance": WalletGetMyBalance(wallet_id),
        "wallet_get_my_address": WalletGetMyAddress(wallet_id),
        "wallet_fund_my_wallet_faucet": WalletFundMyWalletFaucet(wallet_id),
        "wallet_send_stx": WalletSendSTX(wallet_id),
        "wallet_get_my_transactions": WalletGetMyTransactions(wallet_id),
        "wallet_send_sip10": WalletSIP10SendTool(wallet_id),
        "x_credentials": CollectXCredentialsTool(profile_id),
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
