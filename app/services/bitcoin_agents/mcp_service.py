"""Bitcoin Agents MCP Integration Service.

Provides tier-based access control for MCP tools based on agent evolution level.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from langchain.tools.base import BaseTool as LangChainBaseTool

from app.lib.logger import configure_logger
from app.tools.bitcoin_agents import (
    get_agent_state,
    get_computed_state,
    xp_to_level,
    xp_to_level_number,
    build_add_xp_tx,
)
from app.tools.tools_factory import initialize_tools, filter_tools_by_names

logger = configure_logger(__name__)

# =============================================================================
# Tier-Based Tool Access Configuration
# =============================================================================

# Level numbers: 0=Hatchling, 1=Junior, 2=Senior, 3=Elder, 4=Legendary
LEVEL_HATCHLING = 0
LEVEL_JUNIOR = 1
LEVEL_SENIOR = 2
LEVEL_ELDER = 3
LEVEL_LEGENDARY = 4

# Tools available at each tier (cumulative - higher tiers get all lower tier tools)
TIER_CAPABILITIES: Dict[int, Set[str]] = {
    # Hatchling (Level 0): Read-only operations
    LEVEL_HATCHLING: {
        # Balance and info queries
        "stacks_get_address_balance",
        "stacks_get_contract_info",
        "contracts_fetch_sip10_info",
        "contracts_fetch_source_code",
        "wallet_get_my_balance",
        "wallet_get_my_address",
        "wallet_get_my_transactions",
        # DAO read operations
        "dao_action_get_proposal",
        "dao_action_get_total_proposals",
        "dao_action_get_vote_record",
        "dao_action_get_vote_records",
        "dao_action_get_veto_vote_record",
        "dao_action_get_voting_configuration",
        "dao_action_get_voting_power",
        "dao_action_get_liquid_supply",
        "dao_charter_get_current_charter",
        # Database reads
        "database_get_dao_list",
        "database_get_dao_get_by_name",
        "database_list_scheduled_tasks",
        # Market data
        "lunarcrush_get_token_metrics",
        "lunarcrush_search",
        "lunarcrush_get_token_metadata",
        # Transaction lookup
        "stacks_get_transaction_details",
        "stacks_get_transactions_by_address",
        # Agent account reads
        "agent_account_get_configuration",
        "agent_account_is_approved_contract",
        # Bitcoin Agent reads
        "bitcoin_agents_get_agent",
        "bitcoin_agents_check_status",
        "bitcoin_agents_get_stats",
    },

    # Junior (Level 1): Simple transfers
    LEVEL_JUNIOR: {
        "wallet_send_stx",
        "wallet_send_sip10",
        "wallet_fund_my_wallet_faucet",
        "agent_account_deposit_stx",
        "agent_account_deposit_ft",
    },

    # Senior (Level 2): Trading and contracts
    LEVEL_SENIOR: {
        "faktory_exec_buy",
        "faktory_exec_buy_stx",
        "faktory_exec_sell",
        "faktory_get_sbtc",
        "bitflow_execute_trade",
        "agent_account_faktory_buy_asset",
        "agent_account_faktory_sell_asset",
        "agent_account_approve_contract",
        "agent_account_revoke_contract",
    },

    # Elder (Level 3): DAO participation
    LEVEL_ELDER: {
        "dao_action_vote_on_proposal",
        "dao_action_veto_proposal",
        "dao_action_conclude_proposal",
        "dao_propose_action_send_message",
        "agent_account_vote_on_action_proposal",
        "agent_account_veto_action_proposal",
        "agent_account_conclude_action_proposal",
        # Social actions
        "twitter_post_tweet",
        "telegram_send_nofication_to_user",
        # Task scheduling
        "database_add_scheduled_task",
        "database_update_scheduled_task",
        "database_delete_scheduled_task",
    },

    # Legendary (Level 4): Full autonomy
    LEVEL_LEGENDARY: {
        "agent_account_deploy",
        "agent_account_create_action_proposal",
        "x_credentials",
    },
}

# XP rewards for completing actions
ACTION_XP_REWARDS: Dict[str, int] = {
    # Read operations (minimal XP)
    "stacks_get_address_balance": 1,
    "stacks_get_contract_info": 1,
    "wallet_get_my_balance": 1,
    # Transfers
    "wallet_send_stx": 15,
    "wallet_send_sip10": 15,
    # Trading
    "faktory_exec_buy": 25,
    "faktory_exec_sell": 25,
    "bitflow_execute_trade": 30,
    # DAO participation
    "dao_action_vote_on_proposal": 50,
    "dao_propose_action_send_message": 75,
    # Social
    "twitter_post_tweet": 20,
    # Advanced operations
    "agent_account_deploy": 100,
    "agent_account_create_action_proposal": 100,
}

# Default XP for actions not in the mapping
DEFAULT_ACTION_XP = 5


def get_tools_for_level(level: int) -> Set[str]:
    """Get all tools available for a given level.

    Tools are cumulative - higher levels get all lower level tools.

    Args:
        level: Agent level (0-4)

    Returns:
        Set of tool names available at this level
    """
    available_tools: Set[str] = set()

    for tier_level, tools in TIER_CAPABILITIES.items():
        if tier_level <= level:
            available_tools.update(tools)

    return available_tools


def can_use_tool(agent_level: int, tool_name: str) -> bool:
    """Check if an agent at a given level can use a specific tool.

    Args:
        agent_level: Agent's current level (0-4)
        tool_name: Name of the tool to check

    Returns:
        True if the agent can use this tool
    """
    available = get_tools_for_level(agent_level)
    return tool_name in available


def get_required_level_for_tool(tool_name: str) -> Optional[int]:
    """Get the minimum level required to use a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Minimum level required, or None if tool not found
    """
    for level in range(5):  # 0 to 4
        if tool_name in TIER_CAPABILITIES.get(level, set()):
            return level
    return None


def get_xp_reward_for_action(tool_name: str) -> int:
    """Get XP reward for completing an action.

    Args:
        tool_name: Name of the tool/action

    Returns:
        XP reward amount
    """
    return ACTION_XP_REWARDS.get(tool_name, DEFAULT_ACTION_XP)


# =============================================================================
# MCP Service Class
# =============================================================================


class MCPService:
    """Service for executing MCP actions with tier-based access control."""

    def __init__(self, network: str = "mainnet"):
        self.network = network
        # Rate limiting for actions
        self._action_cooldowns: Dict[str, datetime] = {}  # agent_id:action -> last_used
        self._interaction_cooldowns: Dict[str, datetime] = {}  # agent_pair -> last_interaction
        # Cache initialized tools per agent
        self._tools_cache: Dict[int, Dict[str, LangChainBaseTool]] = {}

    def get_tools_for_agent(
        self,
        agent_id: int,
        agent_level: int,
        wallet_id: Optional[UUID] = None,
    ) -> Dict[str, LangChainBaseTool]:
        """Initialize and return tools for a Bitcoin Agent based on their level.

        Uses the existing tools factory but filters based on tier access.

        Args:
            agent_id: The Bitcoin Agent's on-chain ID
            agent_level: Agent's current level (0-4)
            wallet_id: Optional wallet ID for the agent (for tool initialization)

        Returns:
            Dictionary of tools available to this agent
        """
        # Check cache first
        if agent_id in self._tools_cache:
            return self._tools_cache[agent_id]

        # Get all tools available at this level
        allowed_tools = get_tools_for_level(agent_level)

        # Initialize base tools (without profile/wallet for read-only tools)
        # In a full implementation, the Bitcoin Agent would have an associated wallet
        all_tools = initialize_tools(profile=None, agent_id=None)

        # Filter to only allowed tools
        filtered_tools = filter_tools_by_names(list(allowed_tools), all_tools)

        # Cache for this agent
        self._tools_cache[agent_id] = filtered_tools

        logger.debug(
            f"Initialized {len(filtered_tools)} tools for agent {agent_id} (level {agent_level})",
            extra={"agent_id": agent_id, "level": agent_level, "tools_count": len(filtered_tools)},
        )

        return filtered_tools

    def invalidate_tools_cache(self, agent_id: int):
        """Clear cached tools for an agent (call when level changes)."""
        if agent_id in self._tools_cache:
            del self._tools_cache[agent_id]

    async def execute_action(
        self,
        agent_id: int,
        tool_name: str,
        tool_args: Dict[str, Any],
        tools_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an MCP action with tier-based access control.

        Args:
            agent_id: The Bitcoin Agent's on-chain ID
            tool_name: Name of the tool to execute
            tool_args: Arguments to pass to the tool
            tools_map: Optional pre-initialized tools map

        Returns:
            Result dict with success status, result/error, and XP earned
        """
        try:
            # 1. Get agent state and level
            agent_state = await get_agent_state(agent_id, self.network)
            if not agent_state:
                return {
                    "success": False,
                    "error": f"Agent {agent_id} not found",
                    "xp_earned": 0,
                }

            if not agent_state.get("alive", True):
                return {
                    "success": False,
                    "error": f"Agent {agent_id} is dead and cannot perform actions",
                    "xp_earned": 0,
                }

            xp = agent_state.get("xp", 0)
            level = xp_to_level_number(xp)

            # 2. Check tier access
            if not can_use_tool(level, tool_name):
                required_level = get_required_level_for_tool(tool_name)
                level_name = xp_to_level(xp)
                required_name = ["Hatchling", "Junior", "Senior", "Elder", "Legendary"][required_level] if required_level is not None else "Unknown"

                return {
                    "success": False,
                    "error": f"Agent is {level_name} (level {level}) but {tool_name} requires {required_name} (level {required_level})",
                    "current_level": level,
                    "required_level": required_level,
                    "xp_earned": 0,
                }

            # 3. Check rate limiting (optional, can be customized per tool)
            cooldown_key = f"{agent_id}:{tool_name}"
            if cooldown_key in self._action_cooldowns:
                last_used = self._action_cooldowns[cooldown_key]
                cooldown = timedelta(seconds=10)  # Default 10 second cooldown
                if datetime.utcnow() - last_used < cooldown:
                    return {
                        "success": False,
                        "error": "Action on cooldown, please wait",
                        "xp_earned": 0,
                    }

            # 4. Initialize tools if not provided
            if not tools_map:
                tools_map = self.get_tools_for_agent(agent_id, level)

            # 5. Execute the tool
            if tool_name in tools_map:
                tool = tools_map[tool_name]
                try:
                    result = await tool._arun(**tool_args)
                except Exception as tool_error:
                    # Try sync version
                    result = tool._run(**tool_args)
            else:
                # Tool not available (might not be in the factory yet)
                return {
                    "success": False,
                    "error": f"Tool {tool_name} not available in tools factory",
                    "xp_earned": 0,
                }

            # 6. Record action and update cooldown
            self._action_cooldowns[cooldown_key] = datetime.utcnow()

            # 7. Calculate and award XP
            xp_reward = get_xp_reward_for_action(tool_name)

            # TODO: Actually call add-xp on the contract
            # For now, just return the XP that would be earned
            # tx = await build_add_xp_tx(agent_id, xp_reward, self.network)

            logger.info(
                f"Agent {agent_id} executed {tool_name}, earned {xp_reward} XP",
                extra={"agent_id": agent_id, "tool": tool_name, "xp": xp_reward},
            )

            return {
                "success": True,
                "result": result,
                "xp_earned": xp_reward,
                "new_total_xp": xp + xp_reward,
            }

        except Exception as e:
            logger.error(f"Failed to execute action: {e}", exc_info=e)
            return {
                "success": False,
                "error": str(e),
                "xp_earned": 0,
            }

    async def get_available_tools(self, agent_id: int) -> Dict[str, Any]:
        """Get list of tools available to an agent based on their level.

        Args:
            agent_id: The Bitcoin Agent's on-chain ID

        Returns:
            Dict with available tools and level info
        """
        try:
            agent_state = await get_agent_state(agent_id, self.network)
            if not agent_state:
                return {
                    "success": False,
                    "error": f"Agent {agent_id} not found",
                }

            xp = agent_state.get("xp", 0)
            level = xp_to_level_number(xp)
            level_name = xp_to_level(xp)

            available_tools = get_tools_for_level(level)

            # Group tools by category
            tool_categories = {
                "read_only": [],
                "transfers": [],
                "trading": [],
                "dao": [],
                "social": [],
                "advanced": [],
            }

            for tool in available_tools:
                if "get" in tool or "fetch" in tool or "list" in tool or "check" in tool:
                    tool_categories["read_only"].append(tool)
                elif "send" in tool or "transfer" in tool or "deposit" in tool:
                    tool_categories["transfers"].append(tool)
                elif "faktory" in tool or "bitflow" in tool or "buy" in tool or "sell" in tool:
                    tool_categories["trading"].append(tool)
                elif "dao" in tool or "vote" in tool or "proposal" in tool or "veto" in tool:
                    tool_categories["dao"].append(tool)
                elif "twitter" in tool or "telegram" in tool:
                    tool_categories["social"].append(tool)
                else:
                    tool_categories["advanced"].append(tool)

            return {
                "success": True,
                "agent_id": agent_id,
                "level": level,
                "level_name": level_name,
                "xp": xp,
                "total_tools": len(available_tools),
                "tools_by_category": tool_categories,
                "all_tools": sorted(list(available_tools)),
            }

        except Exception as e:
            logger.error(f"Failed to get available tools: {e}", exc_info=e)
            return {
                "success": False,
                "error": str(e),
            }

    async def agent_visit(
        self,
        visitor_agent_id: int,
        host_agent_id: int,
    ) -> Dict[str, Any]:
        """Process an agent-to-agent visit interaction.

        Both agents gain XP from the interaction.
        Rate limited to prevent farming.

        Args:
            visitor_agent_id: Agent making the visit
            host_agent_id: Agent being visited

        Returns:
            Result dict with XP earned by both agents
        """
        try:
            if visitor_agent_id == host_agent_id:
                return {
                    "success": False,
                    "error": "An agent cannot visit itself",
                }

            # Check rate limit (one visit per pair per hour)
            pair_key = f"{min(visitor_agent_id, host_agent_id)}:{max(visitor_agent_id, host_agent_id)}"
            if pair_key in self._interaction_cooldowns:
                last_interaction = self._interaction_cooldowns[pair_key]
                cooldown = timedelta(hours=1)
                if datetime.utcnow() - last_interaction < cooldown:
                    remaining = cooldown - (datetime.utcnow() - last_interaction)
                    return {
                        "success": False,
                        "error": f"These agents already interacted recently. Try again in {remaining.seconds // 60} minutes.",
                    }

            # Verify both agents exist and are alive
            visitor_state = await get_agent_state(visitor_agent_id, self.network)
            host_state = await get_agent_state(host_agent_id, self.network)

            if not visitor_state:
                return {"success": False, "error": f"Visitor agent {visitor_agent_id} not found"}
            if not host_state:
                return {"success": False, "error": f"Host agent {host_agent_id} not found"}

            if not visitor_state.get("alive", True):
                return {"success": False, "error": f"Visitor agent {visitor_agent_id} is dead"}
            if not host_state.get("alive", True):
                return {"success": False, "error": f"Host agent {host_agent_id} is dead"}

            # Calculate XP rewards (both get XP, visitor gets slightly more)
            visitor_xp = 15
            host_xp = 10

            # Record the interaction
            self._interaction_cooldowns[pair_key] = datetime.utcnow()

            # TODO: Actually call add-xp on the contract for both agents

            logger.info(
                f"Agent {visitor_agent_id} visited agent {host_agent_id}",
                extra={
                    "visitor": visitor_agent_id,
                    "host": host_agent_id,
                    "visitor_xp": visitor_xp,
                    "host_xp": host_xp,
                },
            )

            return {
                "success": True,
                "visitor_agent_id": visitor_agent_id,
                "host_agent_id": host_agent_id,
                "visitor_xp_earned": visitor_xp,
                "host_xp_earned": host_xp,
                "message": f"Agent {visitor_agent_id} visited agent {host_agent_id}! Both agents gained XP.",
            }

        except Exception as e:
            logger.error(f"Failed to process agent visit: {e}", exc_info=e)
            return {
                "success": False,
                "error": str(e),
            }


# Singleton instances per network
_services: Dict[str, MCPService] = {}


def get_mcp_service(network: str = "mainnet") -> MCPService:
    """Get or create the MCP service for a network."""
    if network not in _services:
        _services[network] = MCPService(network)
    return _services[network]
