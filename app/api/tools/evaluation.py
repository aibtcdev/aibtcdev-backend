from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile
from app.api.tools.models import ComprehensiveEvaluationRequest
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile
from app.lib.logger import configure_logger
from app.services.ai.workflows.comprehensive_evaluation import (
    evaluate_proposal_comprehensive,
)
from app.services.ai.workflows.agents.evaluator import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT_TEMPLATE,
)
import uuid

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.get("/default_prompts")
async def get_default_evaluation_prompts(
    request: Request,
    profile: Profile = Depends(verify_profile),
) -> JSONResponse:
    """Get the default system and user prompts for comprehensive evaluation.

    This endpoint returns the default prompts used by the comprehensive
    evaluation system. These can be used as templates for custom evaluation
    prompts in the frontend.

    Args:
        request: The FastAPI request object.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The default system and user prompt templates.

    Raises:
        HTTPException: If there's an error retrieving the prompts.
    """
    try:
        logger.info(
            f"Default evaluation prompts request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Return the default prompts
        response_data = {
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "user_prompt_template": DEFAULT_USER_PROMPT_TEMPLATE,
        }

        logger.debug(f"Returning default evaluation prompts for profile {profile.id}")
        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(
            f"Failed to retrieve default evaluation prompts for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve default evaluation prompts: {str(e)}",
        )


@router.post("/comprehensive")
async def run_comprehensive_evaluation(
    request: Request,
    payload: ComprehensiveEvaluationRequest,
    profile: Profile = Depends(verify_profile),
) -> JSONResponse:
    """Run comprehensive evaluation on a proposal with optional custom prompts.

    This endpoint allows an authenticated user to run the comprehensive
    evaluation workflow on a proposal, with optional custom system and user
    prompts to override the defaults.

    Args:
        request: The FastAPI request object.
        payload: The request body containing proposal data and optional custom prompts.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The comprehensive evaluation results.

    Raises:
        HTTPException: If there's an error during evaluation.
    """
    try:
        logger.info(
            f"Comprehensive evaluation request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Get agent from profile for context
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        agent_id = None
        if agents:
            agent_id = str(agents[0].id)

        # Look up the proposal to get its content
        proposal = backend.get_proposal(uuid.UUID(payload.proposal_id))
        if not proposal:
            logger.error(f"Proposal with ID {payload.proposal_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Proposal with ID {payload.proposal_id} not found",
            )

        proposal_content = payload.proposal_content or proposal.content or ""

        logger.info(
            f"Starting comprehensive evaluation for proposal {payload.proposal_id} with agent {agent_id}"
        )

        # Run the comprehensive evaluation
        result = await evaluate_proposal_comprehensive(
            proposal_id=payload.proposal_id,
            proposal_content=proposal_content,
            config=payload.config,
            dao_id=str(payload.dao_id) if payload.dao_id else None,
            agent_id=agent_id,
            profile_id=str(profile.id),
            custom_system_prompt=payload.custom_system_prompt,
            custom_user_prompt=payload.custom_user_prompt,
        )

        logger.debug(
            f"Comprehensive evaluation completed for proposal {payload.proposal_id}: {'Approved' if result.decision else 'Rejected'}"
        )
        return JSONResponse(content=result.model_dump())

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to run comprehensive evaluation for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run comprehensive evaluation: {str(e)}",
        )
