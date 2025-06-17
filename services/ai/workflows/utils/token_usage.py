from typing import Any, Dict

from lib.logger import configure_logger
from lib.utils import calculate_token_cost
from services.ai.workflows.utils.model_factory import get_default_model_name

logger = configure_logger(__name__)


class TokenUsageMixin:
    """Mixin for tracking token usage in LLM calls."""

    def __init__(self):
        """Initialize token usage tracker."""
        pass

    def track_token_usage(self, prompt_text: str, result: Any) -> Dict[str, int]:
        """Track token usage for an LLM invocation.

        Args:
            prompt_text: The prompt text sent to the LLM
            result: The response from the LLM

        Returns:
            Dictionary containing token usage information
        """
        token_usage_data = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        # Try to extract token usage from LLM
        if (
            hasattr(self.llm, "_last_prompt_id")
            and hasattr(self.llm, "client")
            and hasattr(self.llm.client, "usage_by_prompt_id")
        ):
            last_prompt_id = self.llm._last_prompt_id
            if last_prompt_id in self.llm.client.usage_by_prompt_id:
                usage = self.llm.client.usage_by_prompt_id[last_prompt_id]
                token_usage_data = {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }
                return token_usage_data

        # Fallback to estimation
        llm_model_name = getattr(self.llm, "model_name", get_default_model_name())
        token_count = len(prompt_text) // 4  # Simple estimation
        token_usage_dict = {"input_tokens": token_count}
        calculate_token_cost(token_usage_dict, llm_model_name)
        token_usage_data = {
            "input_tokens": token_count,
            "output_tokens": (
                len(result.model_dump_json()) // 4
                if hasattr(result, "model_dump_json")
                else 0
            ),
            "total_tokens": token_count
            + (
                len(result.model_dump_json()) // 4
                if hasattr(result, "model_dump_json")
                else 0
            ),
            "model_name": llm_model_name,
        }
        return token_usage_data
