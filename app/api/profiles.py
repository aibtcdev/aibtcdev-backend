from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.dependencies import verify_faktory_access_token
from app.backend.factory import backend
from app.backend.models import AgentFilter, ProfileFilter, WalletFilter
from app.config import config
from app.lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/profiles")


class ProfileAddresses(BaseModel):
    """Model for profile address information."""

    profile_address: Optional[str] = Field(
        None, description="Profile Stacks address (mainnet or testnet based on config)"
    )
    agent_account_contract: Optional[str] = Field(
        None, description="Agent account contract principal"
    )
    wallet_address: Optional[str] = Field(
        None, description="Wallet Stacks address (mainnet or testnet based on config)"
    )


@router.get("/addresses", response_model=List[ProfileAddresses])
async def get_all_profile_addresses(
    request: Request,
    _: None = Depends(verify_faktory_access_token),
) -> JSONResponse:
    """Get all profile addresses with their associated agent and wallet information.

    This endpoint returns an array of all profiles with their addresses,
    agent account contracts, and wallet addresses. The address type returned
    (mainnet or testnet) is determined by the NETWORK configuration.

    Args:
        request: The FastAPI request object.

    Returns:
        JSONResponse: Array of profile address information.

    Raises:
        HTTPException: If there's an error retrieving the data.
    """
    try:
        logger.info(
            f"Profile addresses request received from {request.client.host if request.client else 'unknown'}"
        )

        # Determine which address field to use based on network configuration
        use_mainnet = config.network.network == "mainnet"
        address_type = "mainnet" if use_mainnet else "testnet"

        logger.debug(f"Using {address_type} addresses based on network configuration")

        # Get all profiles
        profiles = backend.list_profiles(ProfileFilter())

        if not profiles:
            logger.info("No profiles found in the database")
            return JSONResponse(content=[])

        result = []

        for profile in profiles:
            try:
                # Get profile address based on network configuration
                profile_address = (
                    profile.mainnet_address if use_mainnet else profile.testnet_address
                )

                # Initialize profile data
                profile_data = ProfileAddresses(
                    profile_address=profile_address,
                    agent_account_contract=None,
                    wallet_address=None,
                )

                # Get agent for this profile
                agents = backend.list_agents(AgentFilter(profile_id=profile.id))
                if agents:
                    agent = agents[0]  # Take the first agent
                    profile_data.agent_account_contract = agent.account_contract

                    # Get wallet for this agent
                    wallets = backend.list_wallets(WalletFilter(agent_id=agent.id))
                    if wallets:
                        wallet = wallets[0]  # Take the first wallet
                        wallet_address = (
                            wallet.mainnet_address
                            if use_mainnet
                            else wallet.testnet_address
                        )
                        profile_data.wallet_address = wallet_address

                result.append(profile_data)

            except Exception as e:
                logger.warning(f"Error processing profile: {str(e)}")
                # Continue processing other profiles even if one fails
                continue

        logger.info(f"Successfully retrieved address data for {len(result)} profiles")
        return JSONResponse(content=[profile.model_dump() for profile in result])

    except Exception as e:
        logger.error(f"Failed to retrieve profile addresses: {str(e)}", exc_info=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve profile addresses: {str(e)}",
        )
