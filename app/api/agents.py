from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_faktory_access_token
from app.backend.factory import backend
from app.backend.models import AgentFilter, ProfileFilter
from app.lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/agents")


@router.get("/account")
async def get_agent_account_contract(
    request: Request,
    stacks_address: str = Query(..., description="Stacks address (mainnet or testnet)"),
    _: None = Depends(verify_faktory_access_token),
) -> JSONResponse:
    """Get agent account contract by Stacks address.

    This endpoint looks up a profile by Stacks address (mainnet or testnet),
    then finds the associated agent and returns the account_contract.

    Args:
        request: The FastAPI request object.
        stacks_address: The Stacks address to look up.

    Returns:
        JSONResponse: The agent account contract string.

    Raises:
        HTTPException: If the profile or agent is not found.
    """
    try:
        logger.debug(
            "Agent account contract lookup",
            extra={"stacks_address": stacks_address, "event_type": "agent_lookup"},
        )

        # Look up profile by mainnet_address or testnet_address
        profile = None

        # First try mainnet address
        profiles = backend.list_profiles(ProfileFilter(mainnet_address=stacks_address))
        if profiles:
            profile = profiles[0]
            logger.debug(
                "Found profile by mainnet address",
                extra={"profile_id": str(profile.id)},
            )
        else:
            # Try testnet address
            profiles = backend.list_profiles(
                ProfileFilter(testnet_address=stacks_address)
            )
            if profiles:
                profile = profiles[0]
                logger.debug(
                    "Found profile by testnet address",
                    extra={"profile_id": str(profile.id)},
                )

        if not profile:
            logger.warning(
                "Profile not found", extra={"stacks_address": stacks_address}
            )
            raise HTTPException(
                status_code=404,
                detail=f"No profile found for Stacks address: {stacks_address}",
            )

        # Look up agent by profile_id
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.warning("Agent not found", extra={"profile_id": str(profile.id)})
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]
        account_contract = agent.account_contract

        if not account_contract:
            logger.warning(
                "Account contract missing", extra={"agent_id": str(agent.id)}
            )
            raise HTTPException(
                status_code=404,
                detail=f"No account contract found for agent ID: {agent.id}",
            )

        logger.info(
            "Agent account contract retrieved",
            extra={
                "stacks_address": stacks_address,
                "account_contract": account_contract,
            },
        )

        return JSONResponse(content={"account_contract": account_contract})

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            "Agent account contract lookup failed",
            extra={"stacks_address": stacks_address, "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to lookup agent account contract: {str(e)}",
        )
