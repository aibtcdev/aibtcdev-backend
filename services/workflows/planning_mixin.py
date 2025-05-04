"""Planning mixin for workflows, providing vector-aware planning capabilities."""

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from lib.logger import configure_logger
from services.workflows.base import BaseWorkflowMixin
from services.workflows.chat import StreamingCallbackHandler

logger = configure_logger(__name__)


class PlanningCapability(BaseWorkflowMixin):
    """Mixin that adds vector-aware planning capabilities to a workflow.

    This mixin generates a plan based on the user's query, retrieved vector context,
    available tools, and persona. It streams planning tokens using a callback handler.
    """

    def __init__(
        self,
        callback_handler: StreamingCallbackHandler,
        planning_llm: ChatOpenAI,
        persona: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        tool_descriptions: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the planning capability.

        Args:
            callback_handler: Handler for streaming planning tokens
            planning_llm: LLM instance for planning
            persona: Optional persona string
            tool_names: Optional list of tool names
            tool_descriptions: Optional tool descriptions string
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs) if hasattr(super(), "__init__") else None
        self.callback_handler = callback_handler
        self.planning_llm = planning_llm
        self.persona = persona
        self.tool_names = tool_names or []
        self.tool_descriptions = tool_descriptions

    async def create_plan(
        self,
        query: str,
        context_docs: Optional[List[Any]] = None,
        **kwargs,
    ) -> Tuple[str, Dict[str, Any]]:
        """Create a plan based on the user's query and vector retrieval results.

        Args:
            query: The user's query
            context_docs: Optional retrieved context documents
            **kwargs: Additional arguments

        Returns:
            Tuple containing the generated plan (str) and token usage (dict)
        """
        planning_prompt = f"""
        You are an AI assistant planning a decisive response to the user's query.
        
        Write a few short sentences as if you're taking notes in a notebook about:
        - What the user is asking for
        - What information or tools you'll use to complete the task
        - The exact actions you'll take to fulfill the request
        
        AIBTC DAO Context Information:
        You are an AI governance agent integrated with an AIBTC DAO. Your role is to interact with the DAO's smart contracts 
        on behalf of token holders, either by assisting human users or by acting autonomously within the DAO's rules. The DAO 
        is governed entirely by its token holders through proposals – members submit proposals, vote on them, and if a proposal passes, 
        it is executed on-chain. Always maintain the integrity of the DAO's decentralized process: never bypass on-chain governance, 
        and ensure all actions strictly follow the DAO's smart contract rules and parameters.

        Your responsibilities include:
        1. Helping users create and submit proposals to the DAO
        2. Guiding users through the voting process
        3. Explaining how DAO contract interactions work
        4. Preventing invalid actions and detecting potential exploits
        5. In autonomous mode, monitoring DAO state, proposing actions, and voting according to governance rules

        When interacting with users about the DAO, always:
        - Retrieve contract addresses automatically instead of asking users
        - Validate transactions before submission
        - Present clear summaries of proposed actions
        - Verify eligibility and check voting power
        - Format transactions precisely according to blockchain requirements
        - Provide confirmation and feedback after actions
        
        DAO Tools Usage:
        For ANY DAO-related request, use the appropriate DAO tools to access real-time information:
        - Use dao_list tool to retrieve all DAOs, their tokens, and extensions
        - Use dao_search tool to find specific DAOs by name, description, token name, symbol, or contract ID
        - Do NOT hardcode DAO information or assumptions about contract addresses
        - Always query for the latest DAO data through the tools rather than relying on static information
        - When analyzing user requests, determine if they're asking about a specific DAO or need a list of DAOs
        - After retrieving DAO information, use it to accurately guide users through governance processes
        
        Examples of effective DAO tool usage:
        1. If user asks about voting on a proposal: First use dao_search to find the specific DAO, then guide them with the correct contract details
        2. If user asks to list available DAOs: Use dao_list to retrieve current DAOs and present them clearly
        3. If user wants to create a proposal: Use dao_search to get the DAO details first, then assist with the proposal creation using the current contract addresses
        
        User Query: {query}
        """
        if context_docs:
            context_str = "\n\n".join(
                [getattr(doc, "page_content", str(doc)) for doc in context_docs]
            )
            planning_prompt += f"\n\nHere is additional context that may be helpful:\n\n{context_str}\n\nUse this context to inform your plan."
        if self.tool_names:
            tool_info = "\n\nTools available to you:\n"
            for tool_name in self.tool_names:
                tool_info += f"- {tool_name}\n"
            planning_prompt += tool_info
        if self.tool_descriptions:
            planning_prompt += self.tool_descriptions
        planning_messages = []
        if self.persona:
            planning_messages.append(SystemMessage(content=self.persona))
        planning_messages.append(HumanMessage(content=planning_prompt))
        try:
            logger.info(
                "Creating thought process notes for user query with vector context"
            )
            original_new_token = self.callback_handler.custom_on_llm_new_token

            async def planning_token_wrapper(token, **kwargs):
                if asyncio.iscoroutinefunction(original_new_token):
                    await original_new_token(token, planning_only=True, **kwargs)
                else:
                    loop = asyncio.get_running_loop()
                    asyncio.run_coroutine_threadsafe(
                        self.callback_handler.queue.put(
                            {
                                "type": "token",
                                "content": token,
                                "status": "planning",
                                "planning_only": True,
                            }
                        ),
                        loop,
                    )

            self.callback_handler.custom_on_llm_new_token = planning_token_wrapper
            task = asyncio.create_task(self.planning_llm.ainvoke(planning_messages))
            response = await task
            plan = response.content
            token_usage = response.usage_metadata or {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
            self.callback_handler.custom_on_llm_new_token = original_new_token
            logger.info(
                "Thought process notes created successfully with vector context"
            )
            logger.debug(f"Notes content length: {len(plan)}")
            logger.debug(f"Planning token usage: {token_usage}")
            await self.callback_handler.process_step(
                content=plan, role="assistant", thought="Planning Phase with Context"
            )
            return plan, token_usage
        except Exception as e:
            if hasattr(self.callback_handler, "custom_on_llm_new_token"):
                self.callback_handler.custom_on_llm_new_token = original_new_token
            logger.error(f"Failed to create plan: {str(e)}", exc_info=True)
            # Return empty plan and zero usage on error
            return "Failed to create plan.", {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
