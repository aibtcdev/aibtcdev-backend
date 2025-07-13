from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile_from_token
from app.api.tools.models import FaktoryBuyTokenRequest, ToolResponse
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile, WalletFilter
from app.lib.logger import configure_logger
from app.tools.faktory import FaktoryExecuteBuyTool

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.post(
    "/execute_buy",
    response_model=ToolResponse,
    summary="Execute Faktory DEX Buy Order",
    description="Execute a buy order on Faktory DEX to purchase DAO tokens using BTC",
    responses={
        200: {
            "description": "Buy order executed successfully",
            "model": ToolResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Buy order executed successfully",
                        "data": {
                            "transaction_id": "0x1234567890abcdef",
                            "btc_amount": "0.0004",
                            "tokens_received": "1000.000000",
                            "effective_price": "0.0000004",
                            "slippage_used": "15",
                            "block_height": 12345,
                            "dex_contract": "SP1234567890ABCDEF.dao-token-dex",
                        },
                        "error": None,
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {"example": {"detail": "Invalid BTC amount format"}}
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {"example": {"detail": "Invalid bearer token"}}
            },
        },
        404: {
            "description": "Agent or wallet not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No agent found for profile ID: 12345678-1234-1234-1234-123456789abc"
                    }
                }
            },
        },
        500: {
            "description": "Buy order execution failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to execute Faktory buy order: Insufficient liquidity"
                    }
                }
            },
        },
    },
    tags=["faktory"],
)
async def execute_faktory_buy(
    request: Request,
    payload: FaktoryBuyTokenRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """
    Execute a buy order on Faktory DEX.

    This endpoint allows an authenticated user's agent to execute a buy order
    for DAO tokens using BTC on the Faktory decentralized exchange. The order
    is executed with configurable slippage tolerance.

    **Process:**
    1. Validates the user's authentication and retrieves their agent
    2. Finds the agent's associated wallet for transaction signing
    3. Executes the buy order on the Faktory DEX with the specified parameters
    4. Returns the transaction result with trade details

    **Trading Details:**
    - Uses BTC as the base currency for purchases
    - Supports configurable slippage tolerance (default: 15 basis points = 0.15%)
    - Executes immediately at current market prices
    - Returns actual tokens received and effective price

    **Risk Considerations:**
    - Market volatility can affect the final trade price
    - High slippage may result in unfavorable execution
    - Ensure sufficient BTC balance in the agent's wallet
    - Consider market liquidity before large orders

    **Authentication:** Requires Bearer token or API key authentication.
    """
    try:
        logger.info(
            f"Faktory execute buy request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Get agent_id from profile_id
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.error(f"No agent found for profile ID: {profile.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]  # Assuming the first agent is the one to use
        agent_id = agent.id

        # get wallet id from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.error(f"No wallet found for agent ID: {agent_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.info(
            f"Using agent {agent_id} for profile {profile.id} to execute Faktory buy."
        )

        tool = FaktoryExecuteBuyTool(wallet_id=wallet.id)  # Use fetched agent_id
        result = await tool._arun(
            btc_amount=payload.btc_amount,
            dao_token_dex_contract_address=payload.dao_token_dex_contract_address,
            slippage=payload.slippage,
        )

        logger.debug(
            f"Faktory execute buy result for agent {agent_id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(
            f"Failed to execute Faktory buy for profile {profile.id}", exc_info=e
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute Faktory buy order: {str(e)}",
        )
