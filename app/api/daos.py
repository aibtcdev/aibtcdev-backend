from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.dependencies import verify_faktory_access_token
from app.backend.factory import backend
from app.backend.models import (
    HolderFilter,
    TokenFilter,
    ProposalFilter,
    VoteFilter,
    WalletFilter,
)
from app.config import config
from app.lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/daos")


def _agent_voted_in_last_proposals(
    agent_id: str, dao_id: str, last_n_proposals: int
) -> bool:
    """Check if an agent voted in the last N proposals for a DAO.

    Args:
        agent_id: The agent UUID as string
        dao_id: The DAO UUID as string
        last_n_proposals: Number of recent proposals to check

    Returns:
        True if the agent voted in at least one of the last N proposals
    """
    try:
        # Get the last N proposals for this DAO, ordered by creation date desc
        proposals = backend.list_proposals(ProposalFilter(dao_id=dao_id))

        if not proposals:
            return False

        # Sort by created_at descending and take the last N
        proposals.sort(key=lambda p: p.created_at, reverse=True)
        recent_proposals = proposals[:last_n_proposals]

        if not recent_proposals:
            return False

        # Check if agent voted in any of these proposals
        for proposal in recent_proposals:
            votes = backend.list_votes(
                VoteFilter(agent_id=agent_id, proposal_id=proposal.id)
            )
            if votes:
                logger.debug(
                    "Agent voted in proposal",
                    extra={"agent_id": agent_id, "proposal_id": str(proposal.id)},
                )
                return True

        return False

    except Exception as e:
        logger.warning(
            "Error checking voting history",
            extra={"agent_id": agent_id, "error": str(e)},
        )
        return False


def _agent_submitted_proposal(agent_id: str, dao_id: str) -> bool:
    """Check if an agent has ever submitted a proposal for a DAO.

    Args:
        agent_id: The agent UUID as string
        dao_id: The DAO UUID as string

    Returns:
        True if the agent has submitted at least one proposal for this DAO
    """
    try:
        # Get the agent to find their wallet address
        agent = backend.get_agent(agent_id)
        if not agent:
            return False

        # Get the agent's wallet to find their address
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            return False

        wallet = wallets[0]

        # Determine which address to check based on network config
        use_mainnet = config.network.network == "mainnet"
        agent_address = (
            wallet.mainnet_address if use_mainnet else wallet.testnet_address
        )

        if not agent_address:
            return False

        # Check if this agent's address appears as creator in any proposals for this DAO
        proposals = backend.list_proposals(
            ProposalFilter(dao_id=dao_id, creator=agent_address)
        )

        result = len(proposals) > 0
        if result:
            logger.debug(
                "Agent has submitted proposals",
                extra={
                    "agent_id": agent_id,
                    "agent_address": agent_address,
                    "proposal_count": len(proposals),
                },
            )

        return result

    except Exception as e:
        logger.warning(
            "Error checking proposal submission history",
            extra={"agent_id": agent_id, "error": str(e)},
        )
        return False


class TokenHoldersResponse(BaseModel):
    """Model for DAO token holders response."""

    holders: List[str] = Field(
        ..., description="List of agent account contract principals holding the token"
    )


@router.get("/holders", response_model=TokenHoldersResponse)
async def get_dao_token_holders(
    request: Request,
    token_contract_principal: str = Query(
        ..., description="Token contract principal to find holders for"
    ),
    voted_in_last_proposals: Optional[int] = Query(
        None,
        description="Filter to agents who voted in the last X proposals for this token's DAO",
    ),
    has_submitted_proposal: Optional[bool] = Query(
        None,
        description="Filter to agents who have ever submitted a proposal for this token's DAO",
    ),
    _: None = Depends(verify_faktory_access_token),
) -> JSONResponse:
    """Get all agent account contracts that hold a specific DAO token, with optional filters.

    This endpoint takes a token contract principal and returns a list of
    agent account contracts for all agents that hold that token. Results can
    be filtered by voting activity and proposal submission history within the DAO.

    Args:
        request: The FastAPI request object.
        token_contract_principal: The contract principal of the token to find holders for.
        voted_in_last_proposals: Optional filter to only include agents who voted in the last X proposals for this token's DAO.
        has_submitted_proposal: Optional filter to include/exclude agents who have submitted proposals for this token's DAO.

    Returns:
        JSONResponse: List of agent account contract principals that meet the filter criteria.

    Raises:
        HTTPException: If there's an error retrieving the data or token not found.
    """
    try:
        filters_applied = []
        if voted_in_last_proposals is not None:
            filters_applied.append(f"voted_in_last_{voted_in_last_proposals}_proposals")
        if has_submitted_proposal is not None:
            filters_applied.append(f"has_submitted_proposal={has_submitted_proposal}")

        # Build filter info for logging

        logger.debug(
            "DAO token holders request",
            extra={
                "token_contract": token_contract_principal,
                "filters": filters_applied,
                "event_type": "dao_holders",
            },
        )

        # Step 1: Find the token by contract principal
        tokens = backend.list_tokens(
            TokenFilter(contract_principal=token_contract_principal)
        )

        if not tokens:
            logger.warning(
                "Token not found", extra={"token_contract": token_contract_principal}
            )
            raise HTTPException(
                status_code=404,
                detail=f"No token found with contract principal: {token_contract_principal}",
            )

        token = tokens[0]  # Take the first matching token
        logger.debug(
            "Token found",
            extra={
                "token_id": str(token.id),
                "token_contract": token_contract_principal,
            },
        )

        # Step 2: Find all holders of this token
        holders = backend.list_holders(HolderFilter(token_id=token.id))

        if not holders:
            logger.info(
                "No token holders found",
                extra={"token_contract": token_contract_principal},
            )
            return JSONResponse(content={"holders": []})

        logger.debug(
            "Token holders found",
            extra={"count": len(holders), "token_contract": token_contract_principal},
        )

        # Step 3: Get agent account contracts for holders that have agents
        account_contracts = []

        for holder in holders:
            try:
                # Skip holders without agent_id
                if not holder.agent_id:
                    logger.debug(
                        "Holder has no agent", extra={"holder_id": str(holder.id)}
                    )
                    continue

                # Get the agent
                agent = backend.get_agent(holder.agent_id)
                if not agent:
                    logger.warning(
                        "Agent not found for holder",
                        extra={
                            "agent_id": str(holder.agent_id),
                            "holder_id": str(holder.id),
                        },
                    )
                    continue

                # Skip agents without account contracts
                if not agent.account_contract:
                    logger.debug(
                        "Agent missing account contract",
                        extra={"agent_id": str(agent.id)},
                    )
                    continue

                # Apply filters if specified
                if voted_in_last_proposals is not None:
                    if not _agent_voted_in_last_proposals(
                        str(agent.id), str(token.dao_id), voted_in_last_proposals
                    ):
                        logger.debug(
                            "Agent filtered by voting history",
                            extra={
                                "agent_id": str(agent.id),
                                "proposals_checked": voted_in_last_proposals,
                            },
                        )
                        continue

                if has_submitted_proposal is not None:
                    agent_has_submitted = _agent_submitted_proposal(
                        str(agent.id), str(token.dao_id)
                    )
                    if has_submitted_proposal and not agent_has_submitted:
                        logger.debug(
                            "Agent filtered - no proposals submitted",
                            extra={"agent_id": str(agent.id)},
                        )
                        continue
                    elif not has_submitted_proposal and agent_has_submitted:
                        logger.debug(
                            "Agent filtered - has submitted proposals",
                            extra={"agent_id": str(agent.id)},
                        )
                        continue

                # Add account contract if it passes all filters
                account_contracts.append(agent.account_contract)
                logger.debug(
                    "Account contract added",
                    extra={"account_contract": agent.account_contract},
                )

            except Exception as e:
                logger.warning(
                    "Error processing holder",
                    extra={"holder_id": str(holder.id), "error": str(e)},
                )
                # Continue processing other holders even if one fails
                continue

        # Remove duplicates and sort
        unique_contracts = sorted(list(set(account_contracts)))

        logger.info(
            "DAO token holders retrieved",
            extra={
                "token_contract": token_contract_principal,
                "unique_contracts": len(unique_contracts),
                "filters": filters_applied,
            },
        )

        return JSONResponse(content={"holders": unique_contracts})

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            "DAO token holders retrieval failed",
            extra={"token_contract": token_contract_principal, "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve DAO token holders: {str(e)}",
        )
