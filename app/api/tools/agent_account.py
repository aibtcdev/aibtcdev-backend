from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile_from_token
from app.api.tools.models import AgentAccountApproveContractRequest
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile, WalletFilter
from app.lib.logger import configure_logger
from app.tools.agent_account_configuration import AgentAccountApproveContractTool

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.post("/approve_contract")
async def approve_agent_account_contract(
    request: Request,
    payload: AgentAccountApproveContractRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Approve a contract for use with an agent account.

    This endpoint allows an authenticated user's agent to approve a contract,
    enabling the agent account to interact with it.

    Args:
        request: The FastAPI request object.
        payload: The request body containing the agent account contract and contract to approve.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the contract approval operation.

    Raises:
        HTTPException: If there's an error, or if the agent/wallet for the profile is not found.
    """
    try:
        logger.info(
            f"Agent account approve contract request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
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
            f"Using wallet {wallet.id} for profile {profile.id} to approve contract {payload.contract_to_approve} for agent account {payload.agent_account_contract} of type {payload.approval_type}."
        )

        # Initialize and execute the agent account approve contract tool
        tool = AgentAccountApproveContractTool(wallet_id=wallet.id)
        result = await tool._arun(
            agent_account_contract=payload.agent_account_contract,
            contract_to_approve=payload.contract_to_approve,
            approval_type=payload.approval_type,
        )

        logger.debug(
            f"Agent account approve contract result for wallet {wallet.id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to approve contract for agent account for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve contract for agent account: {str(e)}",
        )
