from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.dependencies import verify_faktory_access_token
from app.backend.factory import backend
from app.backend.models import (
    AgentFilter,
    DAOFilter,
    HolderFilter,
    ProfileFilter,
    WalletFilter,
)
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
    dao_name: Optional[str] = None,
    _: None = Depends(verify_faktory_access_token),
) -> JSONResponse:
    """Get all profile addresses with their associated agent and wallet information.

    This endpoint returns an array of all profiles with their addresses,
    agent account contracts, and wallet addresses. The address type returned
    (mainnet or testnet) is determined by the NETWORK configuration.

    Args:
        request: The FastAPI request object.
        dao_name: Optional DAO name to filter results by.

    Returns:
        JSONResponse: Array of profile address information.

    Raises:
        HTTPException: If there's an error retrieving the data.
    """
    try:
        logger.debug(
            "Profile addresses request",
            extra={"dao_name": dao_name, "event_type": "profile_addresses"},
        )

        # Determine which address field to use based on network configuration
        use_mainnet = config.network.network == "mainnet"
        address_type = "mainnet" if use_mainnet else "testnet"

        logger.debug(
            "Network configuration determined",
            extra={"address_type": address_type, "use_mainnet": use_mainnet},
        )

        # Get all profiles
        profiles = backend.list_profiles(ProfileFilter())

        if not profiles:
            logger.info("No profiles found")
            return JSONResponse(content=[])

        # If DAO name filter is provided, find the DAO and filter profiles
        dao_agents = None
        if dao_name:
            daos = backend.list_daos(DAOFilter(name=dao_name))
            if not daos:
                logger.warning("DAO not found", extra={"dao_name": dao_name})
                raise HTTPException(
                    status_code=404,
                    detail=f"DAO with name '{dao_name}' not found",
                )

            dao = daos[0]
            logger.debug(
                "DAO found for filtering",
                extra={"dao_name": dao.name, "dao_id": str(dao.id)},
            )

            # Get all holders for this DAO
            holders = backend.list_holders(HolderFilter(dao_id=dao.id))
            holder_addresses = {holder.address for holder in holders if holder.address}

            logger.debug(
                "Holder addresses found for DAO",
                extra={"count": len(holder_addresses), "dao_name": dao_name},
            )

            # Get agents whose account_contract matches a holder address
            if holder_addresses:
                # Use the efficient batch filtering
                filtered_agents = backend.list_agents(
                    AgentFilter(account_contracts=list(holder_addresses))
                )
                dao_agents = [agent.id for agent in filtered_agents]
            else:
                dao_agents = []

            logger.debug(
                "DAO agents found",
                extra={"count": len(dao_agents), "dao_name": dao_name},
            )

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

                    # If DAO filtering is enabled, skip profiles without agents in the DAO
                    if dao_agents is not None and agent.id not in dao_agents:
                        continue

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
                elif dao_agents is not None:
                    # If DAO filtering is enabled and profile has no agents, skip it
                    continue

                result.append(profile_data)

            except Exception as e:
                logger.warning(
                    "Error processing profile",
                    extra={"profile_id": str(profile.id), "error": str(e)},
                )
                # Continue processing other profiles even if one fails
                continue

        logger.info(
            "Profile addresses retrieved",
            extra={"profile_count": len(result), "dao_name": dao_name},
        )
        return JSONResponse(content=[profile.model_dump() for profile in result])

    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for DAO not found)
        raise
    except Exception as e:
        logger.error(
            "Profile addresses retrieval failed", extra={"error": str(e)}, exc_info=e
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve profile addresses: {str(e)}",
        )
