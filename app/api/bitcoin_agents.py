"""Bitcoin Agents API router.

Provides CRUD endpoints for Tamagotchi-style AI agents with on-chain lifecycle.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from starlette.responses import JSONResponse

from app.backend.models import (
    BitcoinAgent,
    BitcoinAgentFilter,
    BitcoinAgentLevel,
    BitcoinAgentStatus,
    DeathCertificate,
    DeathCertificateFilter,
)
from app.lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/bitcoin-agents", tags=["bitcoin-agents"])

# Contract constants
CONTRACT_ADDRESS_MAINNET = "SP000000000000000000000000000000.bitcoin-agents"  # TODO: Update after deployment
CONTRACT_ADDRESS_TESTNET = "ST000000000000000000000000000000.bitcoin-agents"  # TODO: Update after deployment

# Food tier pricing (in sats)
FOOD_TIERS = {
    1: {"name": "Basic", "cost": 100, "xp": 10},
    2: {"name": "Premium", "cost": 500, "xp": 25},
    3: {"name": "Gourmet", "cost": 1000, "xp": 50},
}

# Mint cost (in sats)
MINT_COST = 10000


@router.get("")
async def list_agents(
    owner: Optional[str] = Query(None, description="Filter by owner address"),
    status: Optional[BitcoinAgentStatus] = Query(None, description="Filter by status (alive/dead)"),
    level: Optional[BitcoinAgentLevel] = Query(None, description="Filter by evolution level"),
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
    limit: int = Query(50, ge=1, le=100, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> JSONResponse:
    """List all Bitcoin Agents with optional filters.

    Returns agents sorted by XP (descending).
    """
    try:
        logger.debug(
            "Listing bitcoin agents",
            extra={"owner": owner, "status": status, "level": level, "network": network},
        )

        # TODO: Implement actual contract reads and database caching
        # For now, return empty list as placeholder
        agents: List[dict] = []

        return JSONResponse(
            content={
                "agents": agents,
                "total": len(agents),
                "limit": limit,
                "offset": offset,
            }
        )

    except Exception as e:
        logger.error("Failed to list bitcoin agents", extra={"error": str(e)}, exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")


@router.get("/leaderboard")
async def get_leaderboard(
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
    limit: int = Query(10, ge=1, le=50, description="Top N agents"),
) -> JSONResponse:
    """Get top agents by XP.

    Returns the leaderboard of highest XP agents.
    """
    try:
        logger.debug("Getting leaderboard", extra={"network": network, "limit": limit})

        # TODO: Implement actual leaderboard query
        leaderboard: List[dict] = []

        return JSONResponse(content={"leaderboard": leaderboard, "network": network})

    except Exception as e:
        logger.error("Failed to get leaderboard", extra={"error": str(e)}, exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to get leaderboard: {str(e)}")


@router.get("/graveyard")
async def get_graveyard(
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> JSONResponse:
    """Get all dead agents (graveyard).

    Returns death certificates sorted by death block (most recent first).
    """
    try:
        logger.debug("Getting graveyard", extra={"network": network})

        # TODO: Implement actual graveyard query
        certificates: List[dict] = []

        return JSONResponse(
            content={
                "certificates": certificates,
                "total": len(certificates),
                "limit": limit,
                "offset": offset,
            }
        )

    except Exception as e:
        logger.error("Failed to get graveyard", extra={"error": str(e)}, exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to get graveyard: {str(e)}")


@router.get("/stats")
async def get_global_stats(
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
) -> JSONResponse:
    """Get global Bitcoin Agents statistics.

    Returns total agents, deaths, feedings, alive count.
    """
    try:
        logger.debug("Getting global stats", extra={"network": network})

        # TODO: Implement actual stats query from contract
        stats = {
            "total_agents": 0,
            "total_deaths": 0,
            "total_feedings": 0,
            "alive_count": 0,
            "network": network,
        }

        return JSONResponse(content=stats)

    except Exception as e:
        logger.error("Failed to get stats", extra={"error": str(e)}, exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/food-tiers")
async def get_food_tiers() -> JSONResponse:
    """Get available food tiers and pricing.

    Returns food tier options with costs and XP rewards.
    """
    return JSONResponse(content={"food_tiers": FOOD_TIERS, "mint_cost": MINT_COST})


@router.get("/{agent_id}")
async def get_agent(
    agent_id: int,
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
) -> JSONResponse:
    """Get a specific agent by ID.

    Returns agent details including computed hunger/health state.
    """
    try:
        logger.debug("Getting agent", extra={"agent_id": agent_id, "network": network})

        # TODO: Implement actual contract read
        # For now, return 404 as placeholder
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent", extra={"agent_id": agent_id, "error": str(e)}, exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")


@router.get("/{agent_id}/status")
async def get_agent_status(
    agent_id: int,
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
) -> JSONResponse:
    """Get computed hunger/health status for an agent.

    Returns current computed state based on blocks elapsed since last fed.
    """
    try:
        logger.debug("Getting agent status", extra={"agent_id": agent_id, "network": network})

        # TODO: Call contract's get-computed-state function
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get agent status",
            extra={"agent_id": agent_id, "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}")


@router.get("/{agent_id}/death-certificate")
async def get_death_certificate(
    agent_id: int,
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
) -> JSONResponse:
    """Get death certificate for a dead agent.

    Returns death certificate details including epitaph if set.
    """
    try:
        logger.debug(
            "Getting death certificate",
            extra={"agent_id": agent_id, "network": network},
        )

        # TODO: Call contract's get-death-certificate function
        raise HTTPException(status_code=404, detail=f"Death certificate for agent {agent_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get death certificate",
            extra={"agent_id": agent_id, "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(status_code=500, detail=f"Failed to get death certificate: {str(e)}")


# =============================================================================
# x402 Payment Endpoints (return 402 with payment requirements)
# =============================================================================


@router.post("/mint")
async def mint_agent_request(
    name: str = Query(..., min_length=1, max_length=64, description="Agent name"),
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
) -> JSONResponse:
    """Request to mint a new agent.

    Returns 402 Payment Required with sBTC payment details.
    After payment is confirmed, execute the mint transaction.
    """
    try:
        logger.info("Mint agent request", extra={"name": name, "network": network})

        # Return 402 with payment requirements
        contract_address = CONTRACT_ADDRESS_MAINNET if network == "mainnet" else CONTRACT_ADDRESS_TESTNET

        payment_details = {
            "status": "payment_required",
            "action": "mint_agent",
            "name": name,
            "cost_sats": MINT_COST,
            "payment_address": contract_address,  # TODO: Use actual payment address
            "network": network,
            "message": f"Send {MINT_COST} sats to mint your Bitcoin Agent '{name}'",
        }

        return JSONResponse(status_code=402, content=payment_details)

    except Exception as e:
        logger.error("Failed to process mint request", extra={"name": name, "error": str(e)}, exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to process mint request: {str(e)}")


@router.post("/{agent_id}/feed")
async def feed_agent_request(
    agent_id: int,
    food_tier: int = Query(..., ge=1, le=3, description="Food tier (1=Basic, 2=Premium, 3=Gourmet)"),
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
) -> JSONResponse:
    """Request to feed an agent.

    Returns 402 Payment Required with sBTC payment details.
    After payment is confirmed, execute the feed transaction.
    """
    try:
        logger.info(
            "Feed agent request",
            extra={"agent_id": agent_id, "food_tier": food_tier, "network": network},
        )

        if food_tier not in FOOD_TIERS:
            raise HTTPException(status_code=400, detail=f"Invalid food tier: {food_tier}")

        food_info = FOOD_TIERS[food_tier]
        contract_address = CONTRACT_ADDRESS_MAINNET if network == "mainnet" else CONTRACT_ADDRESS_TESTNET

        payment_details = {
            "status": "payment_required",
            "action": "feed_agent",
            "agent_id": agent_id,
            "food_tier": food_tier,
            "food_name": food_info["name"],
            "cost_sats": food_info["cost"],
            "xp_reward": food_info["xp"],
            "payment_address": contract_address,  # TODO: Use actual payment address
            "network": network,
            "message": f"Send {food_info['cost']} sats to feed agent {agent_id} with {food_info['name']} food (+{food_info['xp']} XP)",
        }

        return JSONResponse(status_code=402, content=payment_details)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to process feed request",
            extra={"agent_id": agent_id, "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(status_code=500, detail=f"Failed to process feed request: {str(e)}")


@router.post("/{agent_id}/check-death")
async def check_agent_death(
    agent_id: int,
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
) -> JSONResponse:
    """Check if an agent should die and process death if so.

    Anyone can call this to process an agent's death when health reaches 0.
    Returns whether the agent died.
    """
    try:
        logger.info("Check death request", extra={"agent_id": agent_id, "network": network})

        # TODO: Call contract's check-death function
        # This is a public function anyone can call

        return JSONResponse(
            content={
                "agent_id": agent_id,
                "died": False,  # TODO: Actual result from contract
                "message": "Agent is still alive",
            }
        )

    except Exception as e:
        logger.error(
            "Failed to check death",
            extra={"agent_id": agent_id, "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(status_code=500, detail=f"Failed to check death: {str(e)}")


@router.post("/{agent_id}/epitaph")
async def write_epitaph_request(
    agent_id: int,
    epitaph: str = Query(..., min_length=1, max_length=256, description="Memorial text"),
    network: str = Query("mainnet", description="Network (mainnet/testnet)"),
) -> JSONResponse:
    """Write an epitaph for a dead agent.

    Only the owner can write an epitaph, and only once.
    """
    try:
        logger.info(
            "Write epitaph request",
            extra={"agent_id": agent_id, "epitaph_length": len(epitaph), "network": network},
        )

        # TODO: Verify ownership and call contract's write-epitaph function
        raise HTTPException(
            status_code=501,
            detail="Epitaph writing not yet implemented. Requires wallet signature.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to write epitaph",
            extra={"agent_id": agent_id, "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(status_code=500, detail=f"Failed to write epitaph: {str(e)}")
