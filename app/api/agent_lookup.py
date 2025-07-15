from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_agent_lookup_api_key
from app.backend.factory import backend
from app.backend.models import AgentFilter, ProfileFilter
from app.lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.get("/agent_account_contract")
async def get_agent_account_contract(
    request: Request,
    stacks_address: str = Query(..., description="Stacks address (mainnet or testnet)"),
    _: None = Depends(verify_agent_lookup_api_key),
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
        logger.info(
            f"Agent account contract lookup request received from {request.client.host if request.client else 'unknown'} for address: {stacks_address}"
        )

        # Look up profile by mainnet_address or testnet_address
        profile = None

        # First try mainnet address
        profiles = backend.list_profiles(ProfileFilter(mainnet_address=stacks_address))
        if profiles:
            profile = profiles[0]
            logger.info(f"Found profile {profile.id} by mainnet address")
        else:
            # Try testnet address
            profiles = backend.list_profiles(
                ProfileFilter(testnet_address=stacks_address)
            )
            if profiles:
                profile = profiles[0]
                logger.info(f"Found profile {profile.id} by testnet address")

        if not profile:
            logger.error(f"No profile found for Stacks address: {stacks_address}")
            raise HTTPException(
                status_code=404,
                detail=f"No profile found for Stacks address: {stacks_address}",
            )

        # Look up agent by profile_id
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.error(f"No agent found for profile ID: {profile.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]
        account_contract = agent.account_contract

        if not account_contract:
            logger.error(f"No account contract found for agent ID: {agent.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No account contract found for agent ID: {agent.id}",
            )

        logger.info(
            f"Successfully retrieved account contract for address {stacks_address}: {account_contract}"
        )

        return JSONResponse(content={"account_contract": account_contract})

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to lookup agent account contract for address {stacks_address}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to lookup agent account contract: {str(e)}",
        )
