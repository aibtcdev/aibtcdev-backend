from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile
from app.api.tools.models import ComprehensiveEvaluationRequest
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows import evaluate_proposal_strict
from app.services.ai.simple_workflows.evaluation import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT_TEMPLATE,
)
from app.services.ai.simple_workflows.network_school_evaluator import (
    evaluate_user_posts,
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

        logger.info(
            f"Starting comprehensive evaluation for proposal {payload.proposal_id} with agent {agent_id}"
        )

        # Run the comprehensive evaluation using OpenRouter v2
        result = await evaluate_proposal_strict(
            proposal_id=payload.proposal_id,
        )

        if result is None:
            logger.error(
                f"Comprehensive evaluation returned no result for proposal {payload.proposal_id}"
            )
            raise HTTPException(
                status_code=500,
                detail="Comprehensive evaluation failed to produce a result",
            )

        # v2 uses "APPROVE"/"REJECT" instead of boolean
        decision_str = result.decision == "APPROVE"
        logger.debug(
            f"Comprehensive evaluation completed for proposal {payload.proposal_id}: {decision_str}"
        )
        return JSONResponse(content=result)

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


@router.post("/network-school/{username}")
async def evaluate_network_school_posts(
    username: str,
    request: Request,
    profile: Profile = Depends(verify_profile),
) -> JSONResponse:
    """Evaluate Twitter/X posts for Network School alignment.

    This endpoint evaluates a user's recent Twitter/X posts for alignment with
    Network School and startup society ideals. It fetches up to 100 recent posts,
    scores them using Grok's search capabilities, and returns the top posts with
    payout recommendations.

    Args:
        username: Twitter/X username (with or without @ symbol)
        request: The FastAPI request object
        profile: The authenticated user's profile

    Returns:
        JSONResponse: Evaluation results including:
            - username: Twitter username evaluated
            - total_posts_analyzed: Number of posts analyzed
            - top_posts: Top 3 posts with scores, reasons, and payouts
            - usage_input_tokens: Input tokens used
            - usage_output_tokens: Output tokens used
            - usage_est_cost: Estimated cost in USD
            - citations: List of tweet URLs analyzed
            - search_queries: Search queries used by Grok
            - raw_openrouter_response: Complete OpenRouter API response

    Raises:
        HTTPException: If there's an error during evaluation
    """
    try:
        logger.info(
            f"Network School evaluation request for @{username} from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Run the evaluation
        result = await evaluate_user_posts(username)

        logger.info(
            f"Network School evaluation completed for @{username}: "
            f"{len(result.top_posts)} top posts, "
            f"{result.total_posts_analyzed} total analyzed"
        )

        # Convert to dict and exclude raw_openrouter_response for frontend
        response_data = result.model_dump(exclude={"raw_openrouter_response"})

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(
            f"Failed to run Network School evaluation for @{username} (profile {profile.id})",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to evaluate Network School posts: {str(e)}",
        )
