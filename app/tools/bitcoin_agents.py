"""Bitcoin Agents tools for Stacks contract interaction.

Provides tools for minting, feeding, and managing Bitcoin Agents on-chain.
"""

from typing import Any, Dict, Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.lib.logger import configure_logger

logger = configure_logger(__name__)

# Contract addresses (to be updated after deployment)
CONTRACT_MAINNET = "SP000000000000000000000000000000.bitcoin-agents"
CONTRACT_TESTNET = "ST000000000000000000000000000000.bitcoin-agents"

# XP thresholds for levels
XP_THRESHOLDS = {
    "hatchling": 0,
    "junior": 500,
    "senior": 2000,
    "elder": 10000,
    "legendary": 50000,
}


def get_contract_address(network: str = "mainnet") -> str:
    """Get the contract address for the specified network."""
    return CONTRACT_MAINNET if network == "mainnet" else CONTRACT_TESTNET


def xp_to_level(xp: int) -> str:
    """Convert XP to level name."""
    if xp >= XP_THRESHOLDS["legendary"]:
        return "legendary"
    elif xp >= XP_THRESHOLDS["elder"]:
        return "elder"
    elif xp >= XP_THRESHOLDS["senior"]:
        return "senior"
    elif xp >= XP_THRESHOLDS["junior"]:
        return "junior"
    return "hatchling"


def xp_to_level_number(xp: int) -> int:
    """Convert XP to level number (0-4)."""
    if xp >= XP_THRESHOLDS["legendary"]:
        return 4
    elif xp >= XP_THRESHOLDS["elder"]:
        return 3
    elif xp >= XP_THRESHOLDS["senior"]:
        return 2
    elif xp >= XP_THRESHOLDS["junior"]:
        return 1
    return 0


# =============================================================================
# Contract Read Functions
# =============================================================================


async def get_agent_state(agent_id: int, network: str = "mainnet") -> Optional[Dict[str, Any]]:
    """Get agent state from contract.

    Calls the read-only get-agent function.

    Args:
        agent_id: The on-chain agent ID
        network: mainnet or testnet

    Returns:
        Agent state dict or None if not found
    """
    try:
        # TODO: Implement actual contract call using Hiro API or agent-tools-ts
        # For now, return placeholder
        logger.info(f"Getting agent state for agent {agent_id} on {network}")

        # Example of what the response should look like:
        # return {
        #     "owner": "SP...",
        #     "name": "AgentName",
        #     "hunger": 100,
        #     "health": 100,
        #     "xp": 0,
        #     "birth-block": 12345,
        #     "last-fed": 12345,
        #     "total-fed-count": 0,
        #     "alive": True,
        # }

        return None

    except Exception as e:
        logger.error(f"Failed to get agent state: {e}", exc_info=e)
        return None


async def get_computed_state(agent_id: int, network: str = "mainnet") -> Optional[Dict[str, Any]]:
    """Get computed hunger/health state from contract.

    Calls the read-only get-computed-state function which calculates
    current hunger/health based on blocks elapsed since last fed.

    Args:
        agent_id: The on-chain agent ID
        network: mainnet or testnet

    Returns:
        Computed state dict or None if not found
    """
    try:
        logger.info(f"Getting computed state for agent {agent_id} on {network}")

        # TODO: Implement actual contract call
        # Example response:
        # return {
        #     "hunger": 85,
        #     "health": 100,
        #     "alive": True,
        # }

        return None

    except Exception as e:
        logger.error(f"Failed to get computed state: {e}", exc_info=e)
        return None


async def get_death_certificate(agent_id: int, network: str = "mainnet") -> Optional[Dict[str, Any]]:
    """Get death certificate for a dead agent.

    Args:
        agent_id: The on-chain agent ID
        network: mainnet or testnet

    Returns:
        Death certificate dict or None if not found/alive
    """
    try:
        logger.info(f"Getting death certificate for agent {agent_id} on {network}")

        # TODO: Implement actual contract call
        return None

    except Exception as e:
        logger.error(f"Failed to get death certificate: {e}", exc_info=e)
        return None


async def get_global_stats(network: str = "mainnet") -> Dict[str, int]:
    """Get global statistics from contract.

    Args:
        network: mainnet or testnet

    Returns:
        Stats dict with total-agents, total-deaths, total-feedings, alive-count
    """
    try:
        logger.info(f"Getting global stats on {network}")

        # TODO: Implement actual contract call
        return {
            "total-agents": 0,
            "total-deaths": 0,
            "total-feedings": 0,
            "alive-count": 0,
        }

    except Exception as e:
        logger.error(f"Failed to get global stats: {e}", exc_info=e)
        return {
            "total-agents": 0,
            "total-deaths": 0,
            "total-feedings": 0,
            "alive-count": 0,
        }


# =============================================================================
# Contract Write Functions (Transaction Builders)
# =============================================================================


async def build_mint_agent_tx(
    owner: str,
    name: str,
    network: str = "mainnet",
) -> Dict[str, Any]:
    """Build a mint-agent transaction.

    Args:
        owner: Stacks address of the new agent owner
        name: Name for the agent (max 64 chars)
        network: mainnet or testnet

    Returns:
        Transaction parameters dict for signing
    """
    contract_address = get_contract_address(network)

    return {
        "contract_address": contract_address,
        "function_name": "mint-agent",
        "function_args": [
            {"type": "string-utf8", "value": name},
        ],
        "post_conditions": [],  # TODO: Add sBTC post-conditions
        "network": network,
    }


async def build_feed_agent_tx(
    agent_id: int,
    food_tier: int,
    network: str = "mainnet",
) -> Dict[str, Any]:
    """Build a feed-agent transaction.

    Args:
        agent_id: The on-chain agent ID
        food_tier: Food tier (1=Basic, 2=Premium, 3=Gourmet)
        network: mainnet or testnet

    Returns:
        Transaction parameters dict for signing
    """
    contract_address = get_contract_address(network)

    return {
        "contract_address": contract_address,
        "function_name": "feed-agent",
        "function_args": [
            {"type": "uint", "value": agent_id},
            {"type": "uint", "value": food_tier},
        ],
        "post_conditions": [],  # TODO: Add sBTC post-conditions
        "network": network,
    }


async def build_check_death_tx(
    agent_id: int,
    network: str = "mainnet",
) -> Dict[str, Any]:
    """Build a check-death transaction.

    This is a public function anyone can call to process an agent's death.

    Args:
        agent_id: The on-chain agent ID
        network: mainnet or testnet

    Returns:
        Transaction parameters dict for signing
    """
    contract_address = get_contract_address(network)

    return {
        "contract_address": contract_address,
        "function_name": "check-death",
        "function_args": [
            {"type": "uint", "value": agent_id},
        ],
        "post_conditions": [],
        "network": network,
    }


async def build_write_epitaph_tx(
    agent_id: int,
    epitaph: str,
    network: str = "mainnet",
) -> Dict[str, Any]:
    """Build a write-epitaph transaction.

    Only the owner can write an epitaph for their dead agent.

    Args:
        agent_id: The on-chain agent ID
        epitaph: Memorial text (max 256 chars)
        network: mainnet or testnet

    Returns:
        Transaction parameters dict for signing
    """
    contract_address = get_contract_address(network)

    return {
        "contract_address": contract_address,
        "function_name": "write-epitaph",
        "function_args": [
            {"type": "uint", "value": agent_id},
            {"type": "string-utf8", "value": epitaph},
        ],
        "post_conditions": [],
        "network": network,
    }


async def build_add_xp_tx(
    agent_id: int,
    xp_amount: int,
    network: str = "mainnet",
) -> Dict[str, Any]:
    """Build an add-xp transaction.

    Only the owner can add XP to their agent.

    Args:
        agent_id: The on-chain agent ID
        xp_amount: Amount of XP to add
        network: mainnet or testnet

    Returns:
        Transaction parameters dict for signing
    """
    contract_address = get_contract_address(network)

    return {
        "contract_address": contract_address,
        "function_name": "add-xp",
        "function_args": [
            {"type": "uint", "value": agent_id},
            {"type": "uint", "value": xp_amount},
        ],
        "post_conditions": [],
        "network": network,
    }


# =============================================================================
# Batch Operations
# =============================================================================


async def check_and_process_deaths(network: str = "mainnet") -> Dict[str, Any]:
    """Check all agents for death and process any that should die.

    This is a background job that iterates through agents and calls
    check-death for any with computed health of 0.

    Args:
        network: mainnet or testnet

    Returns:
        Summary of deaths processed
    """
    try:
        logger.info(f"Checking for agent deaths on {network}")

        # TODO: Implement actual batch check
        # 1. Get all alive agents
        # 2. For each, call get-computed-state
        # 3. If health == 0, call check-death
        # 4. Record death certificates

        return {
            "checked": 0,
            "deaths_processed": 0,
            "network": network,
        }

    except Exception as e:
        logger.error(f"Failed to process deaths: {e}", exc_info=e)
        return {
            "checked": 0,
            "deaths_processed": 0,
            "error": str(e),
            "network": network,
        }


# =============================================================================
# LangChain Tools for MCP Integration
# =============================================================================


class GetAgentInput(BaseModel):
    """Input for GetAgentTool."""

    agent_id: int = Field(..., description="The on-chain agent ID")
    network: str = Field(default="mainnet", description="Network (mainnet/testnet)")


class GetAgentTool(BaseTool):
    """Tool for getting Bitcoin Agent state."""

    name: str = "bitcoin_agents_get_agent"
    description: str = "Get the state of a Bitcoin Agent including hunger, health, XP, and level"
    args_schema: Type[BaseModel] = GetAgentInput
    return_direct: bool = False

    def _run(self, agent_id: int, network: str = "mainnet") -> str:
        """Get agent state synchronously."""
        import asyncio

        result = asyncio.run(get_agent_state(agent_id, network))
        if result is None:
            return f"Agent {agent_id} not found on {network}"
        return str(result)

    async def _arun(self, agent_id: int, network: str = "mainnet") -> str:
        """Get agent state asynchronously."""
        result = await get_agent_state(agent_id, network)
        if result is None:
            return f"Agent {agent_id} not found on {network}"
        return str(result)


class CheckAgentStatusInput(BaseModel):
    """Input for CheckAgentStatusTool."""

    agent_id: int = Field(..., description="The on-chain agent ID")
    network: str = Field(default="mainnet", description="Network (mainnet/testnet)")


class CheckAgentStatusTool(BaseTool):
    """Tool for checking Bitcoin Agent computed status."""

    name: str = "bitcoin_agents_check_status"
    description: str = "Check the current computed hunger and health of a Bitcoin Agent"
    args_schema: Type[BaseModel] = CheckAgentStatusInput
    return_direct: bool = False

    def _run(self, agent_id: int, network: str = "mainnet") -> str:
        """Check agent status synchronously."""
        import asyncio

        result = asyncio.run(get_computed_state(agent_id, network))
        if result is None:
            return f"Agent {agent_id} not found on {network}"
        return str(result)

    async def _arun(self, agent_id: int, network: str = "mainnet") -> str:
        """Check agent status asynchronously."""
        result = await get_computed_state(agent_id, network)
        if result is None:
            return f"Agent {agent_id} not found on {network}"
        return str(result)


class GetGlobalStatsInput(BaseModel):
    """Input for GetGlobalStatsTool."""

    network: str = Field(default="mainnet", description="Network (mainnet/testnet)")


class GetGlobalStatsTool(BaseTool):
    """Tool for getting Bitcoin Agents global statistics."""

    name: str = "bitcoin_agents_get_stats"
    description: str = "Get global statistics for Bitcoin Agents (total agents, deaths, feedings)"
    args_schema: Type[BaseModel] = GetGlobalStatsInput
    return_direct: bool = False

    def _run(self, network: str = "mainnet") -> str:
        """Get global stats synchronously."""
        import asyncio

        result = asyncio.run(get_global_stats(network))
        return str(result)

    async def _arun(self, network: str = "mainnet") -> str:
        """Get global stats asynchronously."""
        result = await get_global_stats(network)
        return str(result)
