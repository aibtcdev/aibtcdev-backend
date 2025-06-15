from typing import Any, Dict, List, Optional

from lib.logger import configure_logger

logger = configure_logger(__name__)


def no_update_reducer(current: Any, new: List[Any]) -> Any:
    """Reducer that prevents updates after initial value is set.

    Args:
        current: The current value
        new: List of new values to consider

    Returns:
        The original value if set, otherwise the first non-None value from new
    """
    # Treat initial empty string for str types as if it were None for accepting the first value
    is_initial_empty_string = isinstance(current, str) and current == ""

    # If current is genuinely set (not None and not initial empty string), keep it.
    if current is not None and not is_initial_empty_string:
        return current

    # Current is None or an initial empty string. Try to set it from new.
    processed_new_values = (
        new if isinstance(new, list) else [new]
    )  # Ensure 'new' is a list
    for n_val in processed_new_values:
        if n_val is not None:
            return n_val

    # If current was None/initial empty string and new is all None or empty, return current
    return current


def merge_dicts(current: Optional[Dict], updates: List[Optional[Dict]]) -> Dict:
    """Merge multiple dictionary updates into the current dictionary.

    Args:
        current: The current dictionary (or None)
        updates: List of dictionaries to merge in

    Returns:
        The merged dictionary
    """
    # Initialize current if it's None
    if current is None:
        current = {}

    # Handle case where updates is None
    if updates is None:
        return current

    # Process updates if it's a list
    if isinstance(updates, list):
        for update in updates:
            if update and isinstance(update, dict):
                current.update(update)
    # Handle case where updates is a single dictionary, not a list
    elif isinstance(updates, dict):
        current.update(updates)

    return current


def set_once(current: Any, updates: List[Any]) -> Any:
    """Set the value once and prevent further updates.

    Args:
        current: The current value
        updates: List of potential new values

    Returns:
        The current value if set, otherwise the first non-None value from updates
    """
    # If current already has a value, return it unchanged
    if current is not None:
        return current

    # Handle case where updates is None instead of a list
    if updates is None:
        return None

    # Process updates if it's a list
    if isinstance(updates, list):
        for update in updates:
            if update is not None:
                return update
    # Handle case where updates is a single value, not a list
    elif updates is not None:
        return updates

    return current


def update_state_with_agent_result(
    state: Dict[str, Any], agent_result: Dict[str, Any], agent_name: str
) -> Dict[str, Any]:
    """Update state with agent result including summaries and flags.

    Args:
        state: The current state dictionary
        agent_result: The result dictionary from an agent
        agent_name: The name of the agent (e.g., 'core', 'historical')

    Returns:
        The updated state dictionary
    """
    logger.debug(
        f"[DEBUG:update_state:{agent_name}] Updating state with {agent_name}_score (score: {agent_result.get('score', 'N/A')})"
    )

    # Update agent score in state
    if agent_name in ["core", "historical", "financial", "social", "final"]:
        # Make a copy of agent_result to avoid modifying the original
        score_dict = dict(agent_result)
        # Don't pass token_usage through this path to avoid duplication
        if "token_usage" in score_dict:
            del score_dict["token_usage"]

        # Directly assign the dictionary to the state key
        state[f"{agent_name}_score"] = score_dict

    # Update summaries
    if "summaries" not in state:
        state["summaries"] = {}

    if "summary" in agent_result and agent_result["summary"]:
        state["summaries"][f"{agent_name}_score"] = agent_result["summary"]

    # Update flags
    if "flags" not in state:
        state["flags"] = []

    if "flags" in agent_result and isinstance(agent_result["flags"], list):
        state["flags"].extend(agent_result["flags"])

    return state
