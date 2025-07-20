"""Prompt loader utility for simple workflows.

This module provides utilities for loading and managing prompts used by the
simplified workflow system. It automatically discovers prompt modules and
their constants using naming conventions.
"""

import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Optional

from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class PromptLoader:
    """Utility class for loading and managing workflow prompts."""

    def __init__(self):
        """Initialize the prompt loader."""
        self._prompts_cache = {}
        self._modules_cache = {}

    def _get_prompt_modules(self) -> List[str]:
        """Get list of available prompt modules by scanning the directory.

        Returns:
            List of module names (without .py extension)
        """
        prompts_dir = Path(__file__).parent
        prompt_files = []

        for file_path in prompts_dir.glob("*.py"):
            # Skip __init__.py and loader.py
            if file_path.name not in ["__init__.py", "loader.py"]:
                module_name = file_path.stem
                prompt_files.append(module_name)

        return prompt_files

    def _load_prompt_module(self, prompt_type: str):
        """Dynamically load a prompt module.

        Args:
            prompt_type: Type of prompt (e.g., 'evaluation', 'metadata')

        Returns:
            Loaded module or None if failed
        """
        if prompt_type in self._modules_cache:
            return self._modules_cache[prompt_type]

        try:
            module_path = f"app.services.ai.simple_workflows.prompts.{prompt_type}"
            module = importlib.import_module(module_path)
            self._modules_cache[prompt_type] = module
            logger.debug(f"Loaded prompt module: {prompt_type}")
            return module
        except ImportError as e:
            logger.error(f"Failed to import prompt module {prompt_type}: {str(e)}")
            return None

    def _extract_prompts_from_module(self, module, prompt_type: str) -> Dict[str, str]:
        """Extract prompt constants from a module using naming conventions.

        Args:
            module: The loaded module
            prompt_type: Type of prompt for generating expected constant names

        Returns:
            Dictionary of prompt names to prompt texts
        """
        prompts = {}

        # Expected constant names based on naming convention
        prefix = prompt_type.upper()
        system_prompt_name = f"{prefix}_SYSTEM_PROMPT"
        user_template_name = f"{prefix}_USER_PROMPT_TEMPLATE"

        # Try to get the system prompt
        if hasattr(module, system_prompt_name):
            prompts["system"] = getattr(module, system_prompt_name)
            logger.debug(f"Found system prompt: {system_prompt_name}")

        # Try to get the user template
        if hasattr(module, user_template_name):
            prompts["user_template"] = getattr(module, user_template_name)
            logger.debug(f"Found user template: {user_template_name}")

        # Also scan for any other constants that look like prompts
        for name, value in inspect.getmembers(module):
            if (
                isinstance(value, str)
                and name.isupper()
                and ("PROMPT" in name or "TEMPLATE" in name)
                and name not in [system_prompt_name, user_template_name]
            ):
                # Convert constant name to prompt key
                prompt_key = (
                    name.lower().replace(f"{prefix.lower()}_", "").replace("_", "_")
                )
                prompts[prompt_key] = value
                logger.debug(f"Found additional prompt: {name} -> {prompt_key}")

        return prompts

    def load_prompt(self, prompt_type: str, prompt_name: str) -> Optional[str]:
        """Load a prompt by type and name.

        Args:
            prompt_type: Type of prompt (evaluation, metadata, recommendation, etc.)
            prompt_name: Name of the specific prompt (system, user_template, etc.)

        Returns:
            Prompt text or None if not found
        """
        cache_key = f"{prompt_type}.{prompt_name}"

        # Check cache first
        if cache_key in self._prompts_cache:
            return self._prompts_cache[cache_key]

        # Load the module dynamically
        module = self._load_prompt_module(prompt_type)
        if not module:
            return None

        # Extract prompts from module
        prompts = self._extract_prompts_from_module(module, prompt_type)

        # Get the specific prompt
        prompt_text = prompts.get(prompt_name)
        if prompt_text:
            # Cache the prompt
            self._prompts_cache[cache_key] = prompt_text
            logger.debug(f"Loaded prompt: {cache_key}")
            return prompt_text
        else:
            logger.error(f"Prompt not found: {prompt_name} in {prompt_type}")
            logger.debug(f"Available prompts in {prompt_type}: {list(prompts.keys())}")
            return None

    def get_all_prompts(self, prompt_type: str) -> Dict[str, str]:
        """Get all prompts for a specific type.

        Args:
            prompt_type: Type of prompt (evaluation, metadata, recommendation, etc.)

        Returns:
            Dictionary of prompt names to prompt texts
        """
        try:
            # Load the module dynamically
            module = self._load_prompt_module(prompt_type)
            if not module:
                return {}

            # Extract all prompts from module
            prompts = self._extract_prompts_from_module(module, prompt_type)
            logger.debug(f"Retrieved {len(prompts)} prompts for {prompt_type}")
            return prompts

        except Exception as e:
            logger.error(f"Error getting all prompts for {prompt_type}: {str(e)}")
            return {}

    def get_available_prompt_types(self) -> List[str]:
        """Get list of available prompt types by scanning modules.

        Returns:
            List of available prompt types
        """
        return self._get_prompt_modules()

    def clear_cache(self) -> None:
        """Clear the prompts cache."""
        self._prompts_cache.clear()
        self._modules_cache.clear()
        logger.debug("Cleared prompts cache")


# Global prompt loader instance
_prompt_loader = PromptLoader()


def load_prompt(prompt_type: str, prompt_name: str) -> Optional[str]:
    """Convenience function to load a prompt.

    Args:
        prompt_type: Type of prompt (evaluation, metadata, recommendation, etc.)
        prompt_name: Name of the specific prompt (system, user_template, etc.)

    Returns:
        Prompt text or None if not found
    """
    return _prompt_loader.load_prompt(prompt_type, prompt_name)


def get_all_prompts(prompt_type: str) -> Dict[str, str]:
    """Convenience function to get all prompts for a type.

    Args:
        prompt_type: Type of prompt (evaluation, metadata, recommendation, etc.)

    Returns:
        Dictionary of prompt names to prompt texts
    """
    return _prompt_loader.get_all_prompts(prompt_type)


def get_available_prompt_types() -> List[str]:
    """Convenience function to get available prompt types.

    Returns:
        List of available prompt types
    """
    return _prompt_loader.get_available_prompt_types()


def clear_prompts_cache() -> None:
    """Convenience function to clear the prompts cache."""
    _prompt_loader.clear_cache()
