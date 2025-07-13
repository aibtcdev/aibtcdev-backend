from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile
from app.api.tools.models import (
    ComprehensiveEvaluationRequest,
    DefaultPromptsResponse,
    ToolResponse,
)
from app.backend.factory import backend
from app.backend.models import AgentFilter, Profile
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows import evaluate_proposal_comprehensive
from app.services.ai.simple_workflows.evaluation import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT_TEMPLATE,
)
import uuid

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.get(
    "/default_prompts",
    response_model=DefaultPromptsResponse,
    summary="Get Default Evaluation Prompts",
    description="Retrieve the default system and user prompts used for comprehensive proposal evaluation",
    responses={
        200: {
            "description": "Default prompts retrieved successfully",
            "model": DefaultPromptsResponse,
            "content": {
                "application/json": {
                    "example": {
                        "system_prompt": "You are an expert DAO governance evaluator with deep knowledge of blockchain governance.",
                        "user_prompt_template": "Please evaluate the following proposal: {proposal_content}",
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
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to retrieve default evaluation prompts"
                    }
                }
            },
        },
    },
    tags=["evaluation"],
)
async def get_default_evaluation_prompts(
    request: Request,
    profile: Profile = Depends(verify_profile),
) -> JSONResponse:
    """
    Get the default system and user prompts for comprehensive evaluation.

    This endpoint returns the default prompts used by the comprehensive
    evaluation system. These prompts can be used as templates for building
    custom evaluation workflows in frontend applications.

    **Use Cases:**
    - Template for creating custom evaluation prompts
    - Understanding the default evaluation criteria
    - Building evaluation interfaces with pre-configured prompts
    - Customizing evaluation workflows for specific DAOs

    **Prompt Structure:**
    - **System Prompt:** Defines the AI's role and expertise level
    - **User Prompt Template:** Provides the format for evaluation requests

    **Authentication:** Requires Bearer token or API key authentication.
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


@router.post(
    "/comprehensive",
    response_model=ToolResponse,
    summary="Run Comprehensive Proposal Evaluation",
    description="Execute AI-powered comprehensive evaluation of a DAO proposal with detailed analysis and recommendations",
    responses={
        200: {
            "description": "Evaluation completed successfully",
            "model": ToolResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Comprehensive evaluation completed successfully",
                        "data": {
                            "evaluation": {
                                "decision": True,
                                "confidence": 0.85,
                                "reasoning": "The proposal aligns well with the DAO's mission and demonstrates clear value proposition.",
                                "strengths": [
                                    "Clear implementation plan",
                                    "Strong community support",
                                    "Realistic timeline",
                                ],
                                "concerns": [
                                    "Budget allocation needs clarification",
                                    "Risk mitigation could be improved",
                                ],
                                "recommendations": [
                                    "Consider adding milestone-based funding",
                                    "Include performance metrics",
                                ],
                            },
                            "proposal_id": "12345678-1234-1234-1234-123456789abc",
                            "evaluation_timestamp": "2024-01-15T10:30:00Z",
                            "model_used": "gpt-4",
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
                    "example": {"detail": "Invalid proposal ID format"}
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
            "description": "Proposal not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Proposal with ID 12345678-1234-1234-1234-123456789abc not found"
                    }
                }
            },
        },
        500: {
            "description": "Evaluation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to run comprehensive evaluation: AI service unavailable"
                    }
                }
            },
        },
    },
    tags=["evaluation"],
)
async def run_comprehensive_evaluation(
    request: Request,
    payload: ComprehensiveEvaluationRequest,
    profile: Profile = Depends(verify_profile),
) -> JSONResponse:
    """
    Run comprehensive evaluation on a DAO proposal.

    This endpoint executes an AI-powered comprehensive evaluation of a DAO proposal,
    providing detailed analysis, recommendations, and a decision on whether to
    approve or reject the proposal.

    **Evaluation Process:**
    1. Retrieves the proposal content from the database
    2. Analyzes the proposal against DAO governance criteria
    3. Generates detailed evaluation with strengths and concerns
    4. Provides actionable recommendations for improvement
    5. Returns a binary decision with confidence score

    **Evaluation Criteria:**
    - Alignment with DAO mission and values
    - Technical feasibility and implementation plan
    - Resource allocation and budget justification
    - Community impact and stakeholder benefit
    - Risk assessment and mitigation strategies
    - Timeline and milestone clarity

    **Customization Options:**
    - Custom system prompts for specialized evaluation criteria
    - Custom user prompts for specific analysis focus
    - Configurable AI model parameters
    - DAO-specific context integration

    **Authentication:** Requires Bearer token or API key authentication.
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
            proposal_content=proposal_content,
            dao_id=payload.dao_id,
            proposal_id=payload.proposal_id,
            streaming=False,
        )

        evaluation = result.get("evaluation", {})
        logger.debug(
            f"Comprehensive evaluation completed for proposal {payload.proposal_id}: {'Approved' if evaluation.get('decision') else 'Rejected'}"
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
