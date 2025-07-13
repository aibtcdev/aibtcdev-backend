from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile_from_token
from app.api.tools.models import (
    FundWalletFaucetRequest,
    FundSbtcFaucetRequest,
    ToolResponse,
)
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile, WalletFilter
from app.lib.logger import configure_logger
from app.tools.faktory import FaktoryGetSbtcTool
from app.tools.wallet import WalletFundMyWalletFaucet

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.post(
    "/fund_testnet_faucet",
    response_model=ToolResponse,
    summary="Fund Wallet with Testnet STX",
    description="Request testnet STX tokens from the Stacks testnet faucet for development and testing",
    responses={
        200: {
            "description": "Testnet STX funding successful",
            "model": ToolResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Testnet STX funding successful",
                        "data": {
                            "transaction_id": "0x1234567890abcdef",
                            "amount_received": "1000000000",
                            "currency": "STX",
                            "network": "testnet",
                            "wallet_address": "ST1234567890ABCDEF1234567890ABCDEF12345678",
                            "block_height": 12345,
                            "faucet_endpoint": "https://explorer.hiro.so/sandbox/faucet",
                        },
                        "error": None,
                    }
                }
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
            "description": "Faucet request failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to fund wallet with testnet faucet: Faucet rate limit exceeded"
                    }
                }
            },
        },
    },
    tags=["wallet"],
)
async def fund_wallet_with_testnet_faucet(
    request: Request,
    payload: FundWalletFaucetRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """
    Fund wallet with testnet STX tokens using the Stacks testnet faucet.

    This endpoint allows an authenticated user's agent to request testnet STX tokens
    from the official Stacks testnet faucet. These tokens are used for development,
    testing, and experimentation on the Stacks testnet.

    **Testnet Only:** This operation only works on the Stacks testnet environment.
    It will fail if executed on mainnet.

    **Process:**
    1. Validates the user's authentication and retrieves their agent
    2. Finds the agent's associated wallet address
    3. Makes a request to the Stacks testnet faucet
    4. Returns the funding transaction details

    **Faucet Details:**
    - Provides free testnet STX tokens for development
    - Standard amount: ~1,000 STX per request
    - Rate limited to prevent abuse
    - Tokens have no real-world value

    **Use Cases:**
    - Initial wallet funding for new developers
    - Testing DAO governance mechanisms
    - Experimenting with smart contract interactions
    - Building and testing applications on Stacks testnet

    **Rate Limiting:** The faucet implements rate limiting per wallet address
    to prevent abuse. Wait between requests if you encounter rate limit errors.

    **Authentication:** Requires Bearer token or API key authentication.
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


@router.post(
    "/fund_testnet_sbtc",
    response_model=ToolResponse,
    summary="Fund Wallet with Testnet sBTC",
    description="Request testnet sBTC tokens from the Faktory faucet for DeFi testing and development",
    responses={
        200: {
            "description": "Testnet sBTC funding successful",
            "model": ToolResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Testnet sBTC funding successful",
                        "data": {
                            "transaction_id": "0x1234567890abcdef",
                            "amount_received": "100000000",
                            "currency": "sBTC",
                            "network": "testnet",
                            "wallet_address": "ST1234567890ABCDEF1234567890ABCDEF12345678",
                            "block_height": 12345,
                            "faucet_source": "faktory",
                        },
                        "error": None,
                    }
                }
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
            "description": "sBTC faucet request failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to request testnet sBTC from Faktory faucet: Service unavailable"
                    }
                }
            },
        },
    },
    tags=["wallet"],
)
async def fund_with_testnet_sbtc_faucet(
    request: Request,
    payload: FundSbtcFaucetRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """
    Request testnet sBTC tokens from the Faktory faucet.

    This endpoint allows an authenticated user's agent to request testnet sBTC tokens
    from the Faktory faucet. sBTC (Synthetic Bitcoin) is a wrapped Bitcoin token
    on the Stacks blockchain that enables Bitcoin-backed DeFi applications.

    **Testnet Only:** This operation only works on the Stacks testnet environment.
    It will fail if executed on mainnet.

    **Process:**
    1. Validates the user's authentication and retrieves their agent
    2. Finds the agent's associated wallet address
    3. Makes a request to the Faktory sBTC faucet
    4. Returns the funding transaction details

    **sBTC Details:**
    - Synthetic Bitcoin token on Stacks blockchain
    - Backed by real Bitcoin through a peg mechanism
    - Enables Bitcoin-powered DeFi applications
    - Testnet sBTC has no real-world value

    **Use Cases:**
    - Testing DEX trading functionality
    - Experimenting with Bitcoin-backed DeFi protocols
    - Building applications that use sBTC
    - Testing liquidity provision and trading strategies

    **Faktory Integration:** The Faktory faucet provides testnet sBTC specifically
    for testing trading and DeFi functionality on their platform.

    **Rate Limiting:** The faucet implements rate limiting per wallet address
    to prevent abuse. Wait between requests if you encounter rate limit errors.

    **Authentication:** Requires Bearer token or API key authentication.
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
