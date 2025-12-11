"""Network School post evaluator.

Evaluates Twitter/X posts for Network School alignment and quality.
Uses Grok's search capabilities to fetch and score posts.
"""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.evaluation_openrouter_v2 import (
    call_openrouter,
)

logger = configure_logger(__name__)


class PostEvaluation(BaseModel):
    """Evaluation result for a single post."""

    post_url: str = Field(..., description="URL to the tweet")
    score: int = Field(..., ge=0, le=100, description="Score from 0-100")
    reason: str = Field(..., description="1-sentence explanation of the score")
    recommended_payout: str = Field(
        ..., description="Recommended payout in USD (e.g., '$100')"
    )


class NetworkSchoolEvaluationResult(BaseModel):
    """Complete evaluation result."""

    username: str
    total_posts_analyzed: int
    top_posts: List[PostEvaluation] = Field(default_factory=list)
    usage_input_tokens: Optional[int] = None
    usage_output_tokens: Optional[int] = None
    raw_response: Optional[str] = None
    citations: Optional[List[str]] = Field(default_factory=list)
    search_queries: Optional[List[str]] = Field(default_factory=list)
    raw_openrouter_response: Optional[Dict[str, Any]] = None


EVALUATION_PROMPT = """You are evaluating Twitter/X posts for Network School alignment and quality.

IMPORTANT: You must analyze ALL 50 posts and then select the top 3. Do not stop after finding 3 good posts.

Task:
1. Search for and fetch the 50 most recent posts from @{username}
2. Score ALL 50 posts (not just the first few)
3. Return ONLY the top 3 highest-scoring posts

Scoring Criteria (0-100):
- REJECT slop (low effort, generic content)
- REJECT generic positivity (empty cheerleading)
- REWARD clarity (clear, well-articulated ideas)
- REWARD depth (substantive, thoughtful analysis)
- REWARD persuasion (compelling arguments)
- REWARD real work (evidence of actual building/doing)

Process:
1. Use the search tool to find 50 recent posts from @{username}
2. Evaluate and score each of the 50 posts individually
3. Sort all 50 posts by score (highest to lowest)
4. Return ONLY the top 3 posts

Output Format (JSON):
{{
  "total_posts_analyzed": 50,
  "top_posts": [
    {{
      "post_url": "Direct link to the tweet",
      "score": 0-100,
      "reason": "1-sentence explanation",
      "recommended_payout": "$100 or $50 or $25 or $10 or $0"
    }}
  ]
}}

Payout Calculation:
- 90-100: $100
- 80-89: $50
- 70-79: $25
- 60-69: $10
- Below 60: $0

CRITICAL: You must set total_posts_analyzed to the actual number of posts you evaluated."""


async def evaluate_user_posts(username: str) -> NetworkSchoolEvaluationResult:
    """Evaluate recent posts from a Twitter/X user using Grok's search.

    Args:
        username: Twitter/X username (with or without @ symbol)

    Returns:
        NetworkSchoolEvaluationResult with top posts and scores
    """
    # Remove @ if present
    username = username.lstrip("@")

    logger.info(f"Starting evaluation for @{username} using Grok search")

    try:
        prompt = EVALUATION_PROMPT.format(username=username)
        messages = [{"role": "user", "content": prompt}]

        logger.debug(f"Sending evaluation request to Grok for @{username}")

        x_ai_tools = [{"type": "web_search"}, {"type": "x_search"}]
        openrouter_response = await call_openrouter(
            messages=messages,
            model="x-ai/grok-4-fast",
            temperature=0.3,
            tools=x_ai_tools,
        )

        usage = openrouter_response.get("usage") or {}
        usage_input_tokens = usage.get("prompt_tokens")
        usage_output_tokens = usage.get("completion_tokens")
        choices = openrouter_response.get("choices", [])
        if not choices:
            raise ValueError("No choices in OpenRouter response")

        first_choice = choices[0]
        choice_message = first_choice.get("message")
        if not choice_message or not isinstance(choice_message.get("content"), str):
            raise ValueError("Invalid message content in OpenRouter response")

        content = choice_message["content"]
        logger.debug(f"Raw LLM response for @{username}: {content[:500]}...")

        annotations = choice_message.get("annotations") or []
        citations_list: List[str] = []
        search_queries_list: List[str] = []
        for annotation in annotations:
            annotation_type = annotation.get("type")
            if annotation_type == "url_citation":
                url = (annotation.get("url_citation") or {}).get("url")
                if url:
                    citations_list.append(url)
            elif annotation_type == "search_query":
                query = (annotation.get("search_query") or {}).get("query")
                if query:
                    search_queries_list.append(query)

        evaluation_data = json.loads(content)
        if not isinstance(evaluation_data, dict):
            raise ValueError("Evaluation response must be a JSON object")

        evaluation_payload = {
            **evaluation_data,
            "username": username,
            "citations": citations_list,
            "search_queries": search_queries_list,
            "raw_openrouter_response": openrouter_response,
            "usage_input_tokens": usage_input_tokens,
            "usage_output_tokens": usage_output_tokens,
            "raw_response": content[:1000],
        }

        result = NetworkSchoolEvaluationResult(**evaluation_payload)

        logger.info(
            f"Evaluation complete for @{username} - "
            f"analyzed {result.total_posts_analyzed} posts, "
            f"returned {len(result.top_posts)} top posts"
        )

        return result

    except Exception as e:
        logger.error(f"Error evaluating posts for @{username}: {str(e)}")
        raise
