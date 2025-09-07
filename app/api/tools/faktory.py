from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile_from_token
from app.api.tools.models import FaktoryBuyTokenRequest
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile, WalletFilter
from app.lib.logger import configure_logger
from app.tools.faktory import FaktoryExecuteBuyTool

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.post("/execute_buy")
async def execute_faktory_buy(
    request: Request,
    payload: FaktoryBuyTokenRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Execute a buy order on Faktory DEX.

    This endpoint allows an authenticated user's agent to execute a buy order
    for a specified token using BTC on the Faktory DEX.

    Args:
        request: The FastAPI request object.
        payload: The request body containing btc_amount,
                 dao_token_dex_contract_address, and optional slippage.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the buy order execution.

    Raises:
        HTTPException: If there's an error executing the buy order, or if the
                       agent for the profile is not found.
    """
    try:
        logger.debug(
            "Faktory buy request",
            extra={
                "profile_id": str(profile.id),
                "btc_amount": payload.btc_amount,
                "token_contract": payload.dao_token_dex_contract_address,
                "event_type": "faktory_buy",
            },
        )

        # Get agent_id from profile_id
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.warning(
                "Agent not found for profile", extra={"profile_id": str(profile.id)}
            )
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]  # Assuming the first agent is the one to use
        agent_id = agent.id

        # get wallet id from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.warning(
                "Wallet not found for agent", extra={"agent_id": str(agent_id)}
            )
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.debug(
            "Faktory buy initiated",
            extra={"agent_id": str(agent_id), "wallet_id": str(wallet.id)},
        )

        tool = FaktoryExecuteBuyTool(wallet_id=wallet.id)  # Use fetched agent_id
        result = await tool._arun(
            btc_amount=payload.btc_amount,
            dao_token_dex_contract_address=payload.dao_token_dex_contract_address,
            slippage=payload.slippage,
        )

        logger.info(
            "Faktory buy completed",
            extra={
                "agent_id": str(agent_id),
                "profile_id": str(profile.id),
                "success": result.get("success", False),
            },
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(
            "Faktory buy failed",
            extra={"profile_id": str(profile.id), "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute Faktory buy order: {str(e)}",
        )
