from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile_from_token
from app.api.tools.models import FundWalletFaucetRequest, FundSbtcFaucetRequest
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile, WalletFilter
from app.lib.logger import configure_logger
from app.tools.faktory import FaktoryGetSbtcTool
from app.tools.wallet import WalletFundMyWalletFaucet

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.post("/fund_testnet_faucet")
async def fund_wallet_with_testnet_faucet(
    request: Request,
    payload: FundWalletFaucetRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Fund wallet with testnet STX tokens using the faucet.

    This endpoint allows an authenticated user's agent to request testnet STX tokens
    from the Stacks testnet faucet. This operation only works on testnet.

    Args:
        request: The FastAPI request object.
        payload: The request body (empty as no parameters are needed).
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the faucet funding operation.

    Raises:
        HTTPException: If there's an error, or if the agent/wallet for the profile is not found.
    """
    try:
        logger.info(
            f"Wallet testnet faucet request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Get agent from profile
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.error(f"No agent found for profile ID: {profile.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]
        agent_id = agent.id

        # Get wallet from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.error(f"No wallet found for agent ID: {agent_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.info(
            f"Using wallet {wallet.id} for profile {profile.id} to fund with testnet faucet."
        )

        # Initialize and execute the wallet faucet tool
        tool = WalletFundMyWalletFaucet(wallet_id=wallet.id)
        result = await tool._arun()

        logger.debug(
            f"Wallet testnet faucet result for wallet {wallet.id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to fund wallet with testnet faucet for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fund wallet with testnet faucet: {str(e)}",
        )


@router.post("/fund_testnet_sbtc")
async def fund_with_testnet_sbtc_faucet(
    request: Request,
    payload: FundSbtcFaucetRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Request testnet sBTC from the Faktory faucet.

    This endpoint allows an authenticated user's agent to request testnet sBTC tokens
    from the Faktory faucet. This operation only works on testnet.

    Args:
        request: The FastAPI request object.
        payload: The request body (empty as no parameters are needed).
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the sBTC faucet request operation.

    Raises:
        HTTPException: If there's an error, or if the agent/wallet for the profile is not found.
    """
    try:
        logger.info(
            f"Faktory testnet sBTC faucet request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Get agent from profile
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.error(f"No agent found for profile ID: {profile.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]
        agent_id = agent.id

        # Get wallet from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.error(f"No wallet found for agent ID: {agent_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.info(
            f"Using wallet {wallet.id} for profile {profile.id} to request testnet sBTC from Faktory faucet."
        )

        # Initialize and execute the Faktory sBTC faucet tool
        tool = FaktoryGetSbtcTool(wallet_id=wallet.id)
        result = await tool._arun()

        logger.debug(
            f"Faktory testnet sBTC faucet result for wallet {wallet.id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to request testnet sBTC from Faktory faucet for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to request testnet sBTC from Faktory faucet: {str(e)}",
        )
