"""PrePlan ReAct workflow functionality.

This workflow first creates a plan based on the user's query, then executes
the ReAct workflow to complete the task according to the plan.
"""

import asyncio
from typing import Annotated, Any, AsyncGenerator, Dict, List, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from lib.logger import configure_logger
from services.workflows.base import BaseWorkflow, ExecutionError
from services.workflows.react import MessageProcessor, StreamingCallbackHandler

logger = configure_logger(__name__)


class PreplanState(TypedDict):
    """State for the PrePlan ReAct workflow."""

    messages: Annotated[list, add_messages]
    plan: Optional[str]


class PreplanReactWorkflow(BaseWorkflow[PreplanState]):
    """PrePlan ReAct workflow implementation.

    This workflow first creates a plan based on the user's query,
    then executes the ReAct workflow to complete the task according to the plan.
    """

    def __init__(
        self,
        callback_handler: StreamingCallbackHandler,
        tools: List[Any],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.callback_handler = callback_handler
        self.tools = tools
        # Set decisive behavior flag
        self.decisive_behavior = True

        # Create a new LLM instance with the callback handler
        self.llm = ChatOpenAI(
            model=self.llm.model_name,
            temperature=self.llm.temperature,
            streaming=True,
            callbacks=[callback_handler],
        ).bind_tools(tools)

        # Create a separate LLM for planning with streaming enabled
        self.planning_llm = ChatOpenAI(
            model=self.llm.model_name,
            streaming=True,  # Enable streaming for the planning LLM
            temperature=0.2,  # Lower temperature for more structured planning
            callbacks=[callback_handler],
        )

        # Store tool information for planning
        self.tool_names = []
        if tools:
            self.tool_names = [
                tool.name if hasattr(tool, "name") else str(tool) for tool in tools
            ]

    def _create_prompt(self) -> None:
        """Not used in PrePlan ReAct workflow."""
        pass

    async def create_plan(self, query: str) -> str:
        """Create a simple thought process plan based on the user's query."""
        # Create a more decisive planning prompt
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
        
        Be decisive and action-oriented. Don't include phrases like "I would," "I could," or "I might." 
        Instead, use phrases like "I will," "I am going to," and "I'll execute."
        Don't ask for confirmation before taking actions - assume the user wants you to proceed.
        
        User Query: {query}
        """

        # Add available tools to the planning prompt if available
        if hasattr(self, "tool_names") and self.tool_names:
            tool_info = "\n\nTools available to you:\n"
            for tool_name in self.tool_names:
                tool_info += f"- {tool_name}\n"
            planning_prompt += tool_info

        # Add tool descriptions if available
        if hasattr(self, "tool_descriptions"):
            planning_prompt += self.tool_descriptions

        # Create planning messages, including persona if available
        planning_messages = []

        # If we're in the service context and persona is available, add it as a system message
        if hasattr(self, "persona") and self.persona:
            planning_messages.append(SystemMessage(content=self.persona))

        # Add the planning prompt
        planning_messages.append(HumanMessage(content=planning_prompt))

        try:
            logger.info("Creating thought process notes for user query")

            # Configure custom callback for planning to properly mark planning tokens
            original_new_token = self.callback_handler.custom_on_llm_new_token

            # Create temporary wrapper to mark planning tokens
            async def planning_token_wrapper(token, **kwargs):
                # Add planning flag to tokens during the planning phase
                if asyncio.iscoroutinefunction(original_new_token):
                    await original_new_token(token, planning_only=True, **kwargs)
                else:
                    # If it's not a coroutine, assume it's a function that uses run_coroutine_threadsafe
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

            # Set the temporary wrapper
            self.callback_handler.custom_on_llm_new_token = planning_token_wrapper

            # Create a task to invoke the planning LLM
            task = asyncio.create_task(self.planning_llm.ainvoke(planning_messages))

            # Wait for the task to complete
            response = await task
            plan = response.content

            # Restore original callback
            self.callback_handler.custom_on_llm_new_token = original_new_token

            logger.info("Thought process notes created successfully")
            logger.debug(f"Notes content length: {len(plan)}")

            # Use the new process_step method to emit the plan with a planning status
            await self.callback_handler.process_step(
                content=plan, role="assistant", thought="Planning Phase"
            )

            return plan
        except Exception as e:
            # Restore original callback in case of error
            if hasattr(self, "callback_handler") and hasattr(
                self.callback_handler, "custom_on_llm_new_token"
            ):
                self.callback_handler.custom_on_llm_new_token = original_new_token

            logger.error(f"Failed to create plan: {str(e)}", exc_info=True)
            # Let the LLM handle the planning naturally without a static fallback
            raise

    def _create_graph(self) -> StateGraph:
        """Create the PrePlan ReAct workflow graph."""
        logger.info("Creating PrePlan ReAct workflow graph")
        tool_node = ToolNode(self.tools)
        logger.debug(f"Created tool node with {len(self.tools)} tools")

        def should_continue(state: PreplanState) -> str:
            messages = state["messages"]
            last_message = messages[-1]
            result = "tools" if last_message.tool_calls else END
            logger.debug(f"Continue decision: {result}")
            return result

        def call_model(state: PreplanState) -> Dict:
            logger.debug("Calling model with current state")
            messages = state["messages"]

            # Add the plan as a system message if it exists and hasn't been added yet
            if state.get("plan") is not None and not any(
                isinstance(msg, SystemMessage) and "thought" in msg.content.lower()
                for msg in messages
            ):
                logger.info("Adding thought notes to messages as system message")
                plan_message = SystemMessage(
                    content=f"""
                    Follow these decisive actions to address the user's query:
                    
                    {state["plan"]}
                    
                    Execute these steps directly without asking for confirmation.
                    Be decisive and action-oriented in your responses.
                    """
                )
                messages = [plan_message] + messages
            else:
                logger.debug("No thought notes to add or notes already added")

            # If decisive behavior is enabled and there's no plan-related system message,
            # add a decisive behavior system message
            if getattr(self, "decisive_behavior", False) and not any(
                isinstance(msg, SystemMessage) for msg in messages
            ):
                logger.info("Adding decisive behavior instruction as system message")
                decisive_message = SystemMessage(
                    content="Be decisive and take action without asking for confirmation. "
                    "When the user requests something, proceed directly with executing it."
                )
                messages = [decisive_message] + messages

            logger.debug(f"Invoking LLM with {len(messages)} messages")
            response = self.llm.invoke(messages)
            logger.debug("Received model response")
            logger.debug(
                f"Response content length: {len(response.content) if hasattr(response, 'content') else 0}"
            )
            return {"messages": [response]}

        workflow = StateGraph(PreplanState)
        logger.debug("Created StateGraph")

        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")
        logger.info("Graph setup complete")

        return workflow


class PreplanLangGraphService:
    """Service for executing PrePlan LangGraph operations"""

    def __init__(self):
        self.message_processor = MessageProcessor()

    async def execute_preplan_react_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a PrePlan ReAct stream using LangGraph."""
        logger.info("Starting new PrePlan LangGraph ReAct stream execution")
        logger.debug(
            f"Input parameters - History length: {len(history)}, "
            f"Persona present: {bool(persona)}, "
            f"Tools count: {len(tools_map) if tools_map else 0}"
        )

        try:
            callback_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            # Process messages
            filtered_content = self.message_processor.extract_filtered_content(history)
            messages = self.message_processor.convert_to_langchain_messages(
                filtered_content, input_str, persona
            )

            # Setup callback handler
            callback_handler = StreamingCallbackHandler(
                queue=callback_queue,
                on_llm_new_token=lambda token, **kwargs: asyncio.run_coroutine_threadsafe(
                    callback_queue.put(
                        {"type": "token", "content": token, "status": "processing"}
                    ),
                    loop,
                ),
                on_llm_end=lambda *args, **kwargs: asyncio.run_coroutine_threadsafe(
                    callback_queue.put({"type": "end", "status": "complete"}), loop
                ),
            )

            # Create workflow
            workflow = PreplanReactWorkflow(
                callback_handler=callback_handler,
                tools=list(tools_map.values()) if tools_map else [],
            )

            # Store persona and tool information for planning
            if persona:
                # Append decisiveness guidance to the persona
                decisive_guidance = "\n\nBe decisive and take action without asking for confirmation. When the user requests something, proceed directly with executing it rather than asking if they want you to do it."
                workflow.persona = persona + decisive_guidance

            # Store available tool names for planning
            if tools_map:
                workflow.tool_names = list(tools_map.keys())
                # Add tool descriptions to planning prompt
                tool_descriptions = "\n\nTOOL DESCRIPTIONS:\n"
                for name, tool in tools_map.items():
                    description = getattr(
                        tool, "description", "No description available"
                    )
                    tool_descriptions += f"- {name}: {description}\n"
                workflow.tool_descriptions = tool_descriptions

            try:
                # The thought notes will be streamed through callbacks
                plan = await workflow.create_plan(input_str)

            except Exception as e:
                logger.error(f"Planning failed, continuing with execution: {str(e)}")
                yield {
                    "type": "token",
                    "content": "Proceeding directly to answer...\n\n",
                }
                # No plan will be provided, letting the LLM handle the task naturally
                plan = None

            # Create graph and compile
            graph = workflow._create_graph()
            runnable = graph.compile()
            logger.info("Graph compiled successfully")

            # Add the plan to the initial state
            initial_state = {"messages": messages}
            if plan is not None:
                initial_state["plan"] = plan
                logger.info("Added plan to initial state")
            else:
                logger.warning("No plan available for initial state")

            # Set up configuration with callbacks
            config = {"callbacks": [callback_handler]}
            logger.debug("Configuration set up with callbacks")

            # Execute workflow with callbacks config - use the same approach as react.py
            logger.info("Creating task to execute workflow")
            task = asyncio.create_task(runnable.ainvoke(initial_state, config=config))

            # Stream results - use the same approach as react.py
            logger.info("Starting to stream results from callback queue")
            while not task.done():
                try:
                    data = await asyncio.wait_for(callback_queue.get(), timeout=0.1)
                    if data:
                        logger.debug(f"Yielding data of type: {data.get('type')}")
                        yield data
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    logger.error("Task cancelled unexpectedly")
                    task.cancel()
                    raise ExecutionError("Task cancelled unexpectedly")
                except Exception as e:
                    logger.error(f"Error in streaming loop: {str(e)}", exc_info=True)
                    raise ExecutionError(f"Streaming error: {str(e)}")

            # Get final result
            result = await task
            logger.info("Workflow execution completed successfully")
            logger.debug(
                f"Final result content length: {len(result['messages'][-1].content) if result.get('messages') and hasattr(result['messages'][-1], 'content') else 0}"
            )

            # Final yield to indicate completion with type "result" to ensure database storage
            yield {
                "type": "result",
                "content": (
                    result["messages"][-1].content
                    if result.get("messages")
                    and hasattr(result["messages"][-1], "content")
                    else ""
                ),
                "tokens": None,
            }

        except Exception as e:
            logger.error(
                f"Failed to execute PrePlan ReAct stream: {str(e)}", exc_info=True
            )
            raise ExecutionError(f"PrePlan ReAct stream execution failed: {str(e)}")


# Facade function for compatibility with the API
async def execute_preplan_react_stream(
    history: List[Dict],
    input_str: str,
    persona: Optional[str] = None,
    tools_map: Optional[Dict] = None,
) -> AsyncGenerator[Dict, None]:
    """Execute a PrePlan ReAct stream using LangGraph with optional persona."""
    service = PreplanLangGraphService()
    async for chunk in service.execute_preplan_react_stream(
        history, input_str, persona, tools_map
    ):
        yield chunk
