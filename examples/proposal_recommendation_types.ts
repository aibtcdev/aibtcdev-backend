/**
 * TypeScript types and examples for the Proposal Recommendation API
 *
 * This file provides type definitions for the proposal recommendation endpoint
 * and demonstrates how to use them in TypeScript applications.
 */

// ============================================================================
// INPUT TYPES
// ============================================================================

/**
 * Request payload for generating a proposal recommendation
 * Endpoint: POST /tools/dao/proposal_recommendations/generate
 */
export interface ProposalRecommendationRequest {
  /** The UUID of the DAO to generate a proposal recommendation for */
  dao_id: string;

  /**
   * Optional: Specific area of focus for the recommendation
   * Examples: "community growth", "technical development", "partnerships", "governance"
   */
  focus_area?: string;

  /**
   * Optional: Any specific needs or requirements to consider in the recommendation
   */
  specific_needs?: string;

  /**
   * Optional: LLM model to use for generation
   * Examples: "gpt-4.1", "gpt-4o", "gpt-3.5-turbo"
   * Default: "gpt-4.1"
   */
  model_name?: string;

  /**
   * Optional: Temperature for LLM generation (0.0-2.0)
   * Lower values = more focused and deterministic
   * Higher values = more creative and varied
   * Default: 0.1
   */
  temperature?: number;
}

/**
 * HTTP headers required for API authentication
 */
export interface ApiHeaders extends Record<string, string> {
  /** Bearer token for user authentication */
  Authorization: string;

  /** Content type header */
  "Content-Type": "application/json";
}

// ============================================================================
// OUTPUT TYPES
// ============================================================================

/**
 * Priority levels for proposal recommendations
 */
export type ProposalPriority = "high" | "medium" | "low";

/**
 * Token usage tracking information
 */
export interface TokenUsage {
  /** Number of input tokens consumed */
  input_tokens: number;

  /** Number of output tokens generated */
  output_tokens: number;
}

/**
 * Token usage breakdown by agent
 */
export interface TokenUsageBreakdown {
  proposal_recommendation_agent: TokenUsage;
}

/**
 * Main response from the proposal recommendation API
 */
export interface ProposalRecommendationResponse {
  /** A clear, compelling proposal title (max 100 characters) */
  title: string;

  /** Detailed proposal content with objectives, deliverables, timeline, and success metrics */
  content: string;

  /** Explanation of why this proposal is recommended based on the DAO's context */
  rationale: string;

  /** Priority level of the recommendation */
  priority: ProposalPriority;

  /** Expected positive impact on the DAO */
  estimated_impact: string;

  /** Optional: Specific next steps or actions to implement */
  suggested_action?: string;

  // Metadata fields
  /** The DAO identifier that was analyzed */
  dao_id: string;

  /** Name of the DAO */
  dao_name: string;

  /** Number of recent proposals that were analyzed */
  proposals_analyzed: number;

  /** Token usage information for cost tracking */
  token_usage: TokenUsageBreakdown;
}

/**
 * Error response when the API call fails
 */
export interface ProposalRecommendationError {
  /** Error message describing what went wrong */
  error: string;

  /** Empty fields when error occurs */
  title: "";
  content: "";
  rationale: string; // Contains error description
  priority: "low";
  estimated_impact: "None";

  /** DAO metadata if available */
  dao_id?: string;
  dao_name?: string;
}

/**
 * Union type for API response - either success or error
 */
export type ProposalRecommendationResult =
  | ProposalRecommendationResponse
  | ProposalRecommendationError;

// ============================================================================
// EXAMPLE USAGE
// ============================================================================

/**
 * Example of how to call the proposal recommendation API
 */
export async function generateProposalRecommendation(
  request: ProposalRecommendationRequest,
  authToken: string
): Promise<ProposalRecommendationResult> {
  const headers: ApiHeaders = {
    Authorization: `Bearer ${authToken}`,
    "Content-Type": "application/json",
  };

  const response = await fetch("/tools/dao/proposal_recommendations/generate", {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return (await response.json()) as ProposalRecommendationResult;
}

/**
 * Type guard to check if the response is an error
 */
export function isProposalRecommendationError(
  result: ProposalRecommendationResult
): result is ProposalRecommendationError {
  return "error" in result;
}

/**
 * Type guard to check if the response is successful
 */
export function isProposalRecommendationSuccess(
  result: ProposalRecommendationResult
): result is ProposalRecommendationResponse {
  return !("error" in result);
}

// ============================================================================
// USAGE EXAMPLES
// ============================================================================

/**
 * Example 1: Basic usage with minimal input
 */
export const exampleBasicRequest: ProposalRecommendationRequest = {
  dao_id: "12345678-1234-5678-9abc-123456789abc",
};

/**
 * Example 2: Detailed request with focus area and specific needs
 */
export const exampleDetailedRequest: ProposalRecommendationRequest = {
  dao_id: "12345678-1234-5678-9abc-123456789abc",
  focus_area: "community growth",
  specific_needs:
    "We need to increase member engagement and onboard new contributors with technical backgrounds",
};

/**
 * Example 3: Request focused on technical development
 */
export const exampleTechnicalRequest: ProposalRecommendationRequest = {
  dao_id: "87654321-4321-8765-dcba-987654321abc",
  focus_area: "technical development",
  specific_needs:
    "Improve smart contract security, implement new DeFi features, and optimize gas costs",
};

/**
 * Example 4: Request with custom model configuration
 */
export const exampleCustomModelRequest: ProposalRecommendationRequest = {
  dao_id: "11111111-2222-3333-4444-555555555555",
  focus_area: "creative initiatives",
  specific_needs: "Generate innovative and bold proposal ideas",
  model_name: "gpt-4o", // Use the more creative model
  temperature: 0.7, // Higher temperature for more creativity
};

/**
 * Example successful response
 */
export const exampleSuccessResponse: ProposalRecommendationResponse = {
  title: "Community Engagement and Technical Onboarding Initiative",
  content: `## Objective
Establish a comprehensive program to increase member engagement and attract technical contributors to the DAO.

## Deliverables
1. **Developer Onboarding Kit**: Create documentation, tutorials, and coding challenges
2. **Monthly Tech Talks**: Host virtual events featuring DAO projects and external speakers  
3. **Contributor Reward Program**: Implement token-based incentives for code contributions
4. **Mentorship Program**: Pair experienced members with newcomers

## Timeline
- Month 1: Develop onboarding materials and launch mentorship program
- Month 2: Host first tech talk and implement reward system
- Month 3: Evaluate metrics and iterate on program design

## Success Metrics
- 25% increase in active contributors within 3 months
- 50 new technical members onboarded
- 80% satisfaction rate in feedback surveys
- 10+ meaningful code contributions from new members

## Budget
- Content creation: 500 tokens
- Event hosting platform: 200 tokens
- Contributor rewards pool: 1,000 tokens
- Total: 1,700 tokens`,
  rationale:
    "This proposal addresses the DAO's need for increased engagement while specifically targeting technical talent acquisition. Analysis of recent proposals shows a gap in community-building initiatives, and the DAO's mission emphasizes collaborative development. The structured approach with clear metrics ensures accountability and measurable outcomes.",
  priority: "high",
  estimated_impact:
    "Significantly increase community participation, attract quality technical contributors, and establish sustainable growth patterns for the DAO ecosystem",
  suggested_action:
    "Form a Community Development Committee with 3-5 volunteer members to oversee implementation and create detailed project timeline",
  dao_id: "12345678-1234-5678-9abc-123456789abc",
  dao_name: "TechDAO",
  proposals_analyzed: 6,
  token_usage: {
    proposal_recommendation_agent: {
      input_tokens: 1847,
      output_tokens: 423,
    },
  },
};

/**
 * Example error response
 */
export const exampleErrorResponse: ProposalRecommendationError = {
  error: "DAO not found",
  title: "",
  content: "",
  rationale:
    "Error: DAO with ID 12345678-1234-5678-9abc-123456789abc not found",
  priority: "low",
  estimated_impact: "None",
  dao_id: "12345678-1234-5678-9abc-123456789abc",
  dao_name: "Unknown",
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Format the API response for display in UI
 */
export function formatProposalRecommendation(
  response: ProposalRecommendationResponse
): string {
  return `
=== ${response.title} ===
Priority: ${response.priority.toUpperCase()}
DAO: ${response.dao_name}

${response.content}

--- Why This Proposal? ---
${response.rationale}

Expected Impact: ${response.estimated_impact}

${response.suggested_action ? `Next Steps: ${response.suggested_action}` : ""}

Analyzed ${response.proposals_analyzed} recent proposals
Token usage: ${
    response.token_usage.proposal_recommendation_agent.input_tokens
  } input, ${
    response.token_usage.proposal_recommendation_agent.output_tokens
  } output
  `.trim();
}

/**
 * Extract key metrics from the response
 */
export function extractMetrics(response: ProposalRecommendationResponse) {
  return {
    dao: {
      id: response.dao_id,
      name: response.dao_name,
      proposalsAnalyzed: response.proposals_analyzed,
    },
    recommendation: {
      title: response.title,
      priority: response.priority,
      hasActionPlan: !!response.suggested_action,
    },
    tokenUsage: {
      total:
        response.token_usage.proposal_recommendation_agent.input_tokens +
        response.token_usage.proposal_recommendation_agent.output_tokens,
      breakdown: response.token_usage.proposal_recommendation_agent,
    },
  };
}

/**
 * Validate a proposal recommendation request
 */
export function validateRequest(
  request: ProposalRecommendationRequest
): string[] {
  const errors: string[] = [];

  if (!request.dao_id) {
    errors.push("dao_id is required");
  }

  if (request.dao_id && !isValidUUID(request.dao_id)) {
    errors.push("dao_id must be a valid UUID");
  }

  if (request.focus_area && request.focus_area.trim().length === 0) {
    errors.push("focus_area cannot be empty if provided");
  }

  if (request.specific_needs && request.specific_needs.trim().length === 0) {
    errors.push("specific_needs cannot be empty if provided");
  }

  if (request.model_name && request.model_name.trim().length === 0) {
    errors.push("model_name cannot be empty if provided");
  }

  if (request.temperature !== undefined) {
    if (typeof request.temperature !== "number") {
      errors.push("temperature must be a number");
    } else if (request.temperature < 0.0 || request.temperature > 2.0) {
      errors.push("temperature must be between 0.0 and 2.0");
    }
  }

  return errors;
}

/**
 * Simple UUID validation
 */
function isValidUUID(str: string): boolean {
  const uuidRegex =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(str);
}
