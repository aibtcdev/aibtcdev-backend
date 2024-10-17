from crewai_tools import SerperDevTool
from .get_btc_data import GetBitcoinData
from .get_lunar_data import GetLunarData

# from .fetch_contract_code import FetchContractCodeTool


def initialize_tools():
    """
    Initialize and return a dictionary of available tools.
    """
    # NAMES SHOULD BE EXACTLY WHAT'S IN THE FRONTEND
    return {
        "web_search": SerperDevTool(),
        "bitcoin_data": GetBitcoinData(),
        "lunar_data": GetLunarData(),
    }


def get_agent_tools(tool_names, tools_map):
    """
    Get the tools for an agent based on the tool names.

    Args:
        tool_names (list): List of tool names for the agent.
        tools_map (dict): Dictionary mapping tool names to tool instances.

    Returns:
        list: List of tool instances for the agent.
    """
    return [tools_map[name] for name in tool_names if name in tools_map]
