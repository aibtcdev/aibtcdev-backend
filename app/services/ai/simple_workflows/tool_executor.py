"""Simple tool executor for direct tool execution.

This module provides a simple replacement for the complex execute_workflow_stream
function from the old workflows system, allowing direct tool execution without
the complex workflow orchestration.
"""

from typing import Any, AsyncGenerator, Dict, List

from langchain_core.tools import BaseTool

from app.lib.logger import configure_logger

logger = configure_logger(__name__)


async def execute_tool_directly(
    tool_name: str,
    tool: BaseTool,
    tool_input: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a single tool directly with the provided input.

    Args:
        tool_name: Name of the tool to execute
        tool: The tool instance to execute
        tool_input: Input parameters for the tool

    Returns:
        Dictionary containing tool execution results
    """
    try:
        logger.debug(f"Executing tool: {tool_name}")

        # Execute the tool asynchronously
        if hasattr(tool, "_arun"):
            result = await tool._arun(**tool_input)
        else:
            # Fallback to synchronous execution
            result = tool._run(**tool_input)

        logger.debug(f"Tool {tool_name} executed successfully")
        return {
            "success": True,
            "result": result,
            "tool_name": tool_name,
        }
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "tool_name": tool_name,
        }


async def execute_workflow_stream(
    history: List[Dict[str, str]] = None,
    input_str: str = "",
    tools_map: Dict[str, BaseTool] = None,
    **kwargs,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Simple replacement for execute_workflow_stream.

    This function provides a basic streaming interface for tool execution
    without the complex workflow orchestration of the original system.
    For now, it attempts to match tool names from the input string and
    execute them directly.

    Args:
        history: Chat history (currently unused)
        input_str: Input string describing what to do
        tools_map: Dictionary of available tools
        **kwargs: Additional arguments (currently unused)

    Yields:
        Dictionary with execution results in the format expected by callers
    """
    if not tools_map:
        logger.warning("No tools provided to execute_workflow_stream")
        return

    try:
        # For DAO deployment, look for the contract_deploy_dao tool
        if "contract_deploy_dao" in tools_map:
            tool = tools_map["contract_deploy_dao"]
            logger.info("Executing DAO deployment tool")

            # Yield tool start event
            yield {
                "type": "tool",
                "tool": "contract_deploy_dao",
                "status": "started",
                "input": input_str,
                "output": "",
            }

            # Parse the input string to extract parameters
            # This is a simplified parser - in a full implementation you'd use
            # an LLM to parse the natural language input
            tool_params = _parse_dao_deployment_input(input_str)

            # Execute the tool
            result = await execute_tool_directly(
                "contract_deploy_dao",
                tool,
                tool_params,
            )

            # Yield tool completion event
            yield {
                "type": "tool",
                "tool": "contract_deploy_dao",
                "status": "completed",
                "input": input_str,
                "output": result,
            }

            # Yield final result
            yield {
                "type": "result",
                "content": result,
            }
        else:
            logger.warning("No matching tool found for input")
            yield {
                "type": "result",
                "content": {
                    "success": False,
                    "error": "No matching tool found",
                },
            }

    except Exception as e:
        logger.error(f"Error in execute_workflow_stream: {str(e)}")
        yield {
            "type": "result",
            "content": {
                "success": False,
                "error": str(e),
            },
        }


def _parse_dao_deployment_input(input_str: str) -> Dict[str, Any]:
    """Parse DAO deployment parameters from input string.

    This is a simplified parser that extracts parameters from the formatted
    input string used by the DAO deployment task.

    Args:
        input_str: Input string containing DAO deployment parameters

    Returns:
        Dictionary of parsed parameters
    """
    params = {}

    try:
        # Split by lines and extract key-value pairs
        lines = input_str.strip().split("\n")

        for line in lines:
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # Map the human-readable keys to tool parameter names
                if key == "Token Symbol":
                    params["token_symbol"] = value
                elif key == "Token Name":
                    params["token_name"] = value
                elif key == "Token Description":
                    params["token_description"] = value
                elif key == "Token Max Supply":
                    params["token_max_supply"] = value
                elif key == "Token Decimals":
                    params["token_decimals"] = value
                elif key == "Origin Address":
                    params["origin_address"] = value
                elif key == "Mission":
                    params["mission"] = value
                elif key == "Tweet Origin":
                    params["tweet_origin"] = value

        logger.debug(f"Parsed DAO deployment parameters: {params}")
        return params

    except Exception as e:
        logger.error(f"Error parsing DAO deployment input: {str(e)}")
        return {}


async def generate_dao_tweet(
    dao_name: str,
    dao_symbol: str,
    dao_mission: str,
    dao_id: str,
    **kwargs,
) -> Dict[str, Any]:
    """Simple replacement for generate_dao_tweet.

    This function provides basic tweet generation for DAO deployments.
    In a full implementation, this would use an LLM to generate tweets.

    Args:
        dao_name: Name of the DAO
        dao_symbol: Symbol of the DAO token
        dao_mission: Mission statement of the DAO
        dao_id: ID of the DAO
        **kwargs: Additional arguments

    Returns:
        Dictionary containing generated tweet
    """
    try:
        # Generate a simple congratulatory tweet
        tweet_text = (
            f"🎉 Congratulations on the successful deployment of {dao_name} ({dao_symbol})! "
            f"Mission: {dao_mission[:100]}{'...' if len(dao_mission) > 100 else ''} "
            f"#DAO #Bitcoin #AI"
        )

        # Ensure tweet is within character limits
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."

        logger.info(f"Generated tweet for DAO {dao_name}: {tweet_text}")

        return {
            "success": True,
            "tweet_text": tweet_text,
            "dao_id": dao_id,
        }

    except Exception as e:
        logger.error(f"Error generating DAO tweet: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "tweet_text": "",
        }


async def analyze_tweet(
    tweet_data: Dict[str, Any],
    **kwargs,
) -> Dict[str, Any]:
    """Simple replacement for analyze_tweet.

    This function provides basic tweet analysis functionality.
    In a full implementation, this would use an LLM for analysis.

    Args:
        tweet_data: Tweet data to analyze
        **kwargs: Additional arguments

    Returns:
        Dictionary containing analysis results
    """
    try:
        # Basic tweet analysis
        tweet_text = tweet_data.get("text", "")

        analysis = {
            "success": True,
            "sentiment": "neutral",  # Basic sentiment
            "length": len(tweet_text),
            "mentions": tweet_text.count("@"),
            "hashtags": tweet_text.count("#"),
            "contains_dao": "dao" in tweet_text.lower(),
            "contains_bitcoin": "bitcoin" in tweet_text.lower()
            or "btc" in tweet_text.lower(),
        }

        logger.debug(f"Analyzed tweet: {analysis}")
        return analysis

    except Exception as e:
        logger.error(f"Error analyzing tweet: {str(e)}")
        return {
            "success": False,
            "error": str(e),
        }
