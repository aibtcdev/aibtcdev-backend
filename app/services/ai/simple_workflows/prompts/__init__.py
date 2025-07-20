"""Prompts package for simple workflows.

This package contains all the system and user prompts used by the simplified
workflow system, organized by workflow type for easier management.
"""

from .loader import load_prompt, get_all_prompts, get_available_prompt_types
from .evaluation import (
    EVALUATION_SYSTEM_PROMPT,
    EVALUATION_USER_PROMPT_TEMPLATE,
)
from .metadata import (
    METADATA_SYSTEM_PROMPT,
    METADATA_USER_PROMPT_TEMPLATE,
)
from .recommendation import (
    RECOMMENDATION_SYSTEM_PROMPT,
    RECOMMENDATION_USER_PROMPT_TEMPLATE,
)

__all__ = [
    "load_prompt",
    "get_all_prompts",
    "get_available_prompt_types",
    "EVALUATION_SYSTEM_PROMPT",
    "EVALUATION_USER_PROMPT_TEMPLATE",
    "METADATA_SYSTEM_PROMPT",
    "METADATA_USER_PROMPT_TEMPLATE",
    "RECOMMENDATION_SYSTEM_PROMPT",
    "RECOMMENDATION_USER_PROMPT_TEMPLATE",
]
