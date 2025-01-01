import re
from .alex import AlexGetPriceHistory, AlexGetSwapInfo, AlexGetTokenPoolVolume
from .bitflow import BitflowExecuteTradeTool, BitflowGetAvailableTokens
from .contracts import (
    ContractCollectiveDeployTool,
    ContractDAOExecutorDeployTool,
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
)
from backend.models import Profile
from crewai_tools import BaseTool as CrewAIBaseTool
from crewai_tools import DallETool, SerperDevTool
from langchain.tools.base import BaseTool as LangChainBaseTool
from lib.logger import configure_logger
from tools.db import AddScheduledTaskTool
from tools.hiro import STXPriceTool
from typing import Any, Dict, List, Optional

logger = configure_logger(__name__)


def convert_to_langchain_tool(crewai_tool: CrewAIBaseTool) -> LangChainBaseTool:
    """Convert a CrewAI tool to a LangChain tool."""

    class LangChainToolWrapper(LangChainBaseTool):
        # Convert tool name to be OpenAI function compatible
        name: str = re.sub(r"[^a-zA-Z0-9_-]", "_", crewai_tool.name.lower())
        description: str = crewai_tool.description
        args_schema: Optional[type] = crewai_tool.args_schema

        async def _arun(self, *args: Any, **kwargs: Any) -> Any:
            """Run the tool asynchronously."""
            try:
                # If the CrewAI tool has an async run method, use it
                if hasattr(crewai_tool, "_arun"):
                    if not self.args_schema:
                        return await crewai_tool._arun()
                    return await crewai_tool._arun(*args, **kwargs)
                # Otherwise, run synchronously
                if not self.args_schema:
                    return crewai_tool._run()
                return crewai_tool._run(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error running tool {self.name}: {str(e)}")
                raise

        def _run(self, *args: Any, **kwargs: Any) -> Any:
            """Run the tool synchronously."""
            try:
                if not self.args_schema:
                    return crewai_tool._run()
                return crewai_tool._run(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error running tool {self.name}: {str(e)}")
                raise

        @property
        def args(self) -> Dict:
            """Get the tool's arguments schema."""
            if not self.args_schema:
                # Return empty dict for tools with no input
                return {}
            return super().args

    tool = LangChainToolWrapper()
    logger.debug(f"Converting tool: {crewai_tool.name} -> {tool.name}")
    return tool


def initialize_tools(profile: Profile) -> Dict[str, CrewAIBaseTool]:
    """Initialize and return a dictionary of available CrewAI tools."""
    # Convert account_index to string
    account_index = (
        str(profile.account_index) if profile.account_index is not None else "0"
    )

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
        "db_add_scheduled_task": AddScheduledTaskTool(profile.id),
        "web_search_experimental": SerperDevTool(),
        "velar_get_token_price_history": VelarGetPriceHistory(),
        "velar_get_tokens": VelarGetTokens(),
        "wallet_get_my_balance": WalletGetMyBalance(account_index),
        "wallet_get_my_address": WalletGetMyAddress(account_index),
        "wallet_fund_my_wallet_faucet": WalletFundMyWalletFaucet(account_index),
        "wallet_send_stx": WalletSendSTX(account_index),
        "wallet_get_my_transactions": WalletGetMyTransactions(account_index),
        "stacks_transaction_status": StacksTransactionStatusTool(),
        "stacks_transaction": StacksTransactionTool(),
        "stacks_transaction_by_address": StacksTransactionByAddressTool(),
        # "contract_sip10_deploy": ContractSIP10DeployTool(account_index),
        "contract_sip10_send": ContractSIP10SendTool(account_index),
        "contract_sip10_info": ContractSIP10InfoTool(account_index),
        "contract_collective_deploy": ContractCollectiveDeployTool(account_index),
        # "contract_dao_executor_deploy": ContractDAOExecutorDeployTool(account_index),
        "fetch_contract_code": FetchContractCodeTool(),
        "get_btc_data": GetBitcoinData(),
        "image_generation": DallETool(),
        "get_stx_price": STXPriceTool(),
    }


def get_agent_tools(
    tool_names: List[str], tools_map: Dict[str, CrewAIBaseTool]
) -> List[CrewAIBaseTool]:
    """Get CrewAI tools for an agent based on the tool names."""
    return [tools_map[name] for name in tool_names if name in tools_map]


def initialize_langchain_tools(profile: Profile) -> Dict[str, LangChainBaseTool]:
    """Initialize and return a dictionary of available LangChain tools."""
    crewai_tools = initialize_tools(profile)
    langchain_tools = {}

    for name, tool in crewai_tools.items():
        try:
            langchain_tool = convert_to_langchain_tool(tool)
            # Use sanitized tool name as key
            sanitized_name = langchain_tool.name
            langchain_tools[sanitized_name] = langchain_tool
            logger.debug(f"Successfully converted tool {name} -> {sanitized_name}")
        except Exception as e:
            logger.error(f"Failed to convert tool {name}: {str(e)}")
            continue

    logger.debug(
        f"Initialized {len(langchain_tools)} LangChain tools: {list(langchain_tools.keys())}"
    )
    return langchain_tools


def get_langchain_agent_tools(
    tool_names: List[str], tools_map: Dict[str, LangChainBaseTool]
) -> List[LangChainBaseTool]:
    """Get LangChain tools for an agent based on the tool names."""
    return [tools_map[name] for name in tool_names if name in tools_map]
