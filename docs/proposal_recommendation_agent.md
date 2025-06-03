# Proposal Recommendation Agent

The `ProposalRecommendationAgent` is a LangGraph-based AI agent that generates intelligent proposal recommendations for DAOs based on their mission, description, and historical proposal data.

## Overview

This agent analyzes a DAO's context and provides thoughtful suggestions for new proposals that:
- Align with the DAO's mission and values
- Build upon or complement existing proposals
- Address gaps in the DAO's current proposal landscape
- Are practical and achievable

## Features

- **Mission Alignment**: Analyzes the DAO's mission statement and description to ensure recommendations align with core values
- **Historical Context**: Reviews up to 8 recent proposals to understand patterns, avoid duplicates, and identify gaps
- **Intelligent Analysis**: Uses AI to identify opportunities for meaningful proposals that would benefit the DAO
- **Structured Output**: Returns well-formatted recommendations with titles, content, rationale, priority, and impact assessments
- **Token Usage Tracking**: Monitors and reports LLM token consumption for cost management

## Architecture

The agent follows the established LangGraph workflow patterns:

```python
from services.workflows.agents.proposal_recommendation import ProposalRecommendationAgent
from services.workflows.utils.models import ProposalRecommendationOutput
```

### Key Components

1. **ProposalRecommendationAgent**: Main agent class inheriting from `BaseCapabilityMixin` and `TokenUsageMixin`
2. **ProposalRecommendationOutput**: Pydantic model defining the structured output format
3. **Database Integration**: Direct integration with Supabase through the backend factory
4. **API Endpoint**: RESTful API endpoint for authenticated users

## Usage

### Direct Agent Usage

```python
import asyncio
from uuid import UUID
from services.workflows.agents.proposal_recommendation import ProposalRecommendationAgent

async def get_recommendation():
    agent = ProposalRecommendationAgent(config={})
    
    state = {
        "dao_id": UUID("your-dao-id-here"),
        "focus_area": "community growth",  # Optional
        "specific_needs": "Increase member engagement"  # Optional
    }
    
    result = await agent.process(state)
    return result
```

### API Usage

**Endpoint**: `POST /tools/dao/proposal_recommendations/generate`

**Authentication**: Requires valid user session token

**Request Body**:
```json
{
    "dao_id": "12345678-1234-5678-9abc-123456789abc",
    "focus_area": "technical development",
    "specific_needs": "Improve smart contract security"
}
```

**Response**:
```json
{
    "title": "Smart Contract Security Audit and Enhancement Program",
    "content": "Comprehensive proposal with objectives, deliverables, timeline...",
    "rationale": "Based on the DAO's mission and analysis of recent proposals...",
    "priority": "high",
    "estimated_impact": "Significantly improve contract security and member confidence",
    "suggested_action": "Form a security committee and allocate budget for audits",
    "dao_id": "12345678-1234-5678-9abc-123456789abc",
    "dao_name": "Example DAO",
    "proposals_analyzed": 5,
    "token_usage": {
        "proposal_recommendation_agent": {
            "input_tokens": 1250,
            "output_tokens": 340
        }
    }
}
```

## Output Schema

The agent returns a `ProposalRecommendationOutput` with the following fields:

- **title** (string): A clear, compelling proposal title (max 100 characters)
- **content** (string): Detailed proposal content with objectives, deliverables, timeline, and success metrics
- **rationale** (string): Explanation of why this proposal is recommended based on DAO context
- **priority** (string): Priority level - "high", "medium", or "low"
- **estimated_impact** (string): Expected positive impact on the DAO
- **suggested_action** (string, optional): Specific next steps or actions to implement

Additional metadata includes:
- **dao_id**: The DAO identifier
- **dao_name**: Name of the DAO
- **proposals_analyzed**: Number of recent proposals analyzed
- **token_usage**: LLM token consumption details

## Analysis Criteria

The agent evaluates proposals based on:

1. **Alignment with DAO Mission** (40%): How well the recommendation aligns with stated mission and values
2. **Gap Analysis** (25%): Identifying opportunities not addressed by recent proposals
3. **Feasibility** (20%): Practical achievability and resource requirements
4. **Community Impact** (15%): Potential positive impact on the DAO community

## Configuration Options

The agent accepts configuration options through the `config` parameter:

```python
config = {
    "recursion_limit": 20,  # Maximum processing recursion
    "model_name": "gpt-4.1",  # LLM model to use
    "temperature": 0.1,  # LLM temperature setting
}

agent = ProposalRecommendationAgent(config=config)
```

## Error Handling

The agent includes comprehensive error handling:

- **DAO Not Found**: Returns error response if the specified DAO doesn't exist
- **Database Errors**: Gracefully handles database connection issues
- **LLM Errors**: Catches and reports AI model errors
- **Validation Errors**: Validates input parameters and provides clear error messages

## Integration with Existing Systems

The agent seamlessly integrates with the existing aibtcdev-backend architecture:

- **Backend Factory**: Uses the established backend pattern for database access
- **Authentication**: Leverages existing user authentication via `verify_profile_from_token`
- **Logging**: Uses the configured logger for consistent log output
- **Models**: Follows the Pydantic model patterns used throughout the codebase

## Example Use Cases

1. **Regular Proposal Planning**: DAOs can use this monthly to identify new proposal opportunities
2. **Gap Analysis**: Understanding what areas need attention based on proposal history
3. **Strategic Planning**: Generating ideas that align with long-term DAO goals
4. **Member Engagement**: Providing starting points for community members to create proposals

## Future Enhancements

Potential improvements could include:

- Integration with vector stores for semantic similarity analysis
- Support for proposal templates and categories
- Budget estimation and resource planning
- Integration with DAO voting history and outcomes
- Multi-language support for international DAOs

## Testing

See `examples/proposal_recommendation_example.py` for a complete usage example and testing script. 