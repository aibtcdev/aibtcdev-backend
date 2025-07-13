from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile_from_token
from app.api.tools.models import AgentAccountApproveContractRequest, ToolResponse
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile, WalletFilter
from app.lib.logger import configure_logger
from app.tools.agent_account_configuration import AgentAccountApproveContractTool

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.post(
    "/approve_contract",
    response_model=ToolResponse,
    summary="Approve Contract for Agent Account",
    description="Allow an agent account to interact with a specified smart contract by approving it",
    responses={
        200: {
            "description": "Contract approval successful",
            "model": ToolResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Contract approved successfully",
                        "data": {
                            "transaction_id": "0x1234567890abcdef",
                            "agent_account_contract": "SP1234567890ABCDEF.agent-account-v1",
                            "approved_contract": "SP1234567890ABCDEF.dao-contract-to-approve",
                            "block_height": 12345,
                        },
                        "error": None,
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid contract principal format"}
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
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to approve contract for agent account: Network error"
                    }
                }
            },
        },
    },
    tags=["agent-account"],
)
async def approve_agent_account_contract(
    request: Request,
    payload: AgentAccountApproveContractRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """
    Approve a contract for use with an agent account.

    This endpoint allows an authenticated user's agent to approve a smart contract,
    enabling the agent account to interact with it. This is a prerequisite for
    the agent account to call functions on the approved contract.

    **Process:**
    1. Validates the user's authentication and retrieves their agent
    2. Finds the agent's associated wallet for transaction signing
    3. Executes the contract approval transaction on the Stacks blockchain
    4. Returns the transaction result with confirmation details

    **Use Cases:**
    - Approve DAO contracts for governance participation
    - Enable interaction with DeFi protocols
    - Grant access to specific smart contract functions
    - Set up permissions for automated agent operations

    **Authentication:** Requires Bearer token or API key authentication.
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
            f"Using wallet {wallet.id} for profile {profile.id} to approve contract {payload.contract_to_approve} for agent account {payload.agent_account_contract}."
        )

        # Initialize and execute the agent account approve contract tool
        tool = AgentAccountApproveContractTool(wallet_id=wallet.id)
        result = await tool._arun(
            agent_account_contract=payload.agent_account_contract,
            contract_to_approve=payload.contract_to_approve,
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
