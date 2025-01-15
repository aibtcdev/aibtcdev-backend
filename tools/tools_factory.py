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
from crewai_tools import BaseTool as CrewAIBaseTool
from langchain.tools.base import BaseTool as LangChainBaseTool
from lib.logger import configure_logger
from pydantic import BaseModel, create_model
from typing import Any, Callable, Dict, List, Optional, Type

logger = configure_logger(__name__)


def initialize_tools(
    profile: Profile,
    agent_id: Optional[UUID] = None,
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

    if not agent_id:
        wallet = backend.list_wallets(filters=WalletFilter(profile_id=profile.id))[0]
        if not wallet:
            raise ValueError("No wallet found for profile")
        wallet_id = wallet.id
    else:
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
        "dao_list": GetDAOListTool(),
        "dao_get_by_name": GetDAOByNameTool(),
        "db_list_scheduled_tasks": ListScheduledTasksTool(profile.id, agent_id),
        "db_update_scheduled_task": UpdateScheduledTaskTool(profile.id, agent_id),
        "db_delete_scheduled_task": DeleteScheduledTaskTool(profile.id, agent_id),
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
        # "contract_sip10_deploy": ContractSIP10DeployTool(wallet_id),
        # "contract_dao_executor_deploy": ContractDAOExecutorDeployTool(wallet_id),
        "contract_sip10_info": ContractSIP10InfoTool(wallet_id),
        "contract_dao_deploy": ContractDAODeployTool(wallet_id),
        "contract_source_fetch": FetchContractSourceTool(wallet_id),
        "btc_price": GetBitcoinData(),
        "stxcity_search": StxCitySearchTool(wallet_id),
        "stxcity_execute_sell": StxCityExecuteSellTool(wallet_id),
        "stxcity_execute_buy": StxCityExecuteBuyTool(wallet_id),
        "stxcity_check_valid_bonding": StxCityCheckValidBondingTool(wallet_id),
        "stxcity_list_bonding_tokens": StxCityListBondingTokensTool(wallet_id),
        "twitter_post_tweet": TwitterPostTweetTool(profile.id, agent_id),
        "dao_core_get_linked_voting_contracts": CoreGetLinkedVotingContractsTool(
            wallet_id
        ),
        "dao_core_create_proposal": CoreCreateProposalTool(wallet_id),
        "dao_core_get_proposal": CoreGetProposalTool(wallet_id),
        "dao_core_get_total_votes": CoreGetTotalVotesTool(wallet_id),
        "dao_core_get_voting_power": CoreGetVotingPowerTool(wallet_id),
        "dao_core_vote_on_proposal": CoreVoteOnProposalTool(wallet_id),
        "dao_core_conclude_proposal": CoreConcludeProposalTool(wallet_id),
        "dao_action_get_linked_voting_contracts": ActionGetLinkedVotingContractsTool(
            wallet_id
        ),
        "dao_action_get_proposal": ActionGetProposalTool(wallet_id),
        "dao_action_get_total_votes": ActionGetTotalVotesTool(wallet_id),
        "dao_action_get_voting_power": ActionGetVotingPowerTool(wallet_id),
        "dao_action_vote_on_proposal": ActionVoteOnProposalTool(wallet_id),
        "dao_action_conclude_proposal": ActionConcludeProposalTool(wallet_id),
        "dao_action_get_total_proposals": ActionGetTotalProposalsTool(wallet_id),
        "dao_buy_token": BuyTokenTool(wallet_id),
        "dao_sell_token": SellTokenTool(wallet_id),
        # DAO Propose Action Tools
        "dao_propose_action_add_resource": ProposeActionAddResourceTool(wallet_id),
        "dao_propose_action_allow_asset": ProposeActionAllowAssetTool(wallet_id),
        "dao_propose_action_send_message": ProposeActionSendMessageTool(wallet_id),
        "dao_propose_action_set_account_holder": ProposeActionSetAccountHolderTool(
            wallet_id
        ),
        "dao_propose_action_set_withdrawal_amount": ProposeActionSetWithdrawalAmountTool(
            wallet_id
        ),
        "dao_propose_action_set_withdrawal_period": ProposeActionSetWithdrawalPeriodTool(
            wallet_id
        ),
        "dao_propose_action_toggle_resource": ProposeActionToggleResourceTool(
            wallet_id
        ),
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


class BaseAIBTCTool(CrewAIBaseTool):
    """Base class for AIBTC tools with necessary configuration."""

    model_config = {"arbitrary_types_allowed": True}
    _func: Optional[Callable[..., Any]] = None

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool with the given arguments."""
        if self._func is None:
            raise NotImplementedError("Tool must implement _run or provide a function")
        return self._func(*args, **kwargs)

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool asynchronously."""
        if inspect.iscoroutinefunction(self._func):
            return await self._func(*args, **kwargs)
        return self._run(*args, **kwargs)


def create_dynamic_tool_model(
    name: str,
    description: str,
    args_schema: Optional[Type[BaseModel]] = None,
    return_direct: bool = False,
    **extra_fields: Any,
) -> Type[BaseAIBTCTool]:
    """Create a dynamic Pydantic model for a tool with additional fields."""

    # Create the dynamic model class
    model = create_model(
        f"Dynamic{name.replace(' ', '')}Tool",
        __base__=BaseAIBTCTool,
        name=(str, name),
        description=(str, description),
        args_schema=(Optional[Type[BaseModel]], args_schema),
        return_direct=(bool, return_direct),
        **{k: v for k, v in extra_fields.items()},
    )

    return model


def convert_langchain_to_crewai(langchain_tool: LangChainBaseTool) -> CrewAIBaseTool:
    """Convert a LangChain tool into a CrewAI tool."""
    # Get all attributes from the langchain tool that we might want to preserve
    extra_fields = {}
    for attr in dir(langchain_tool):
        if not attr.startswith("_") and attr not in (
            "name",
            "description",
            "args_schema",
            "return_direct",
            "func",
            "run",
            "arun",
            "model_computed_fields",  # Exclude Pydantic internal field
            "model_config",  # Exclude Pydantic internal field
            "model_fields",  # Exclude Pydantic internal field
        ):
            value = getattr(langchain_tool, attr)
            if not callable(value):
                # Create a tuple of (type, default_value) for each field
                extra_fields[attr] = (type(value), value)

    # Create the dynamic model class
    DynamicTool = create_dynamic_tool_model(
        name=langchain_tool.name,
        description=langchain_tool.description,
        args_schema=getattr(langchain_tool, "args_schema", None),
        return_direct=getattr(langchain_tool, "return_direct", False),
        **extra_fields,
    )

    # Create an instance of the dynamic model
    tool_instance = DynamicTool()
    tool_instance._func = langchain_tool._run

    return tool_instance
