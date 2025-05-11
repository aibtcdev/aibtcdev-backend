import asyncio
from typing import (
    Annotated,
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    TypedDict,
    Union,
)

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from backend.factory import backend
from lib.logger import configure_logger
from services.workflows.base import (
    BaseWorkflow,
    ExecutionError,
    MessageProcessor,
    StreamingCallbackHandler,
)
from services.workflows.planning_mixin import PlanningCapability
from services.workflows.vector_mixin import (
    VectorRetrievalCapability,
)
from services.workflows.web_search_mixin import WebSearchCapability

logger = configure_logger(__name__)


class ChatState(TypedDict):
    """State for the Chat workflow, combining all capabilities."""

    messages: Annotated[list, add_messages]
    vector_results: Optional[List[Document]]
    web_search_results: Optional[List[Document]]  # Web search results
    plan: Optional[str]


class ChatWorkflow(
    BaseWorkflow[ChatState],
    PlanningCapability,
    VectorRetrievalCapability,
    WebSearchCapability,
):
    """Workflow that combines vector retrieval and planning capabilities.

    This workflow:
    1. Retrieves relevant context from multiple vector stores
    2. Creates a plan based on the user's query and retrieved context
    3. Executes the ReAct workflow with both context and plan
    """

    def __init__(
        self,
        callback_handler: StreamingCallbackHandler,
        tools: List[Any],
        collection_names: Union[
            str, List[str]
        ],  # Modified to accept single or multiple collections
        embeddings: Optional[Embeddings] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.callback_handler = callback_handler
        self.tools = tools
        # Convert single collection to list for consistency
        self.collection_names = (
            [collection_names]
            if isinstance(collection_names, str)
            else collection_names
        )
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.required_fields = ["messages"]

        # Decisive behavior flag (from PreplanReactWorkflow)
        self.decisive_behavior = True

        # Create a new LLM instance with the callback handler
        self.llm = self.create_llm_with_callbacks([callback_handler]).bind_tools(tools)

        # Create a separate LLM for planning with streaming enabled
        self.planning_llm = ChatOpenAI(
            model="o4-mini",
            streaming=True,
            callbacks=[callback_handler],
        )

        # Store tool information for planning
        self.tool_names = []
        if tools:
            self.tool_names = [
                tool.name if hasattr(tool, "name") else str(tool) for tool in tools
            ]

        # Additional attributes for planning
        self.persona = None
        self.tool_descriptions = None

        # Initialize mixins
        PlanningCapability.__init__(
            self,
            callback_handler=callback_handler,
            planning_llm=self.planning_llm,
            persona=self.persona,
            tool_names=self.tool_names,
            tool_descriptions=self.tool_descriptions,
        )
        VectorRetrievalCapability.__init__(self)
        WebSearchCapability.__init__(self)

    def _create_prompt(self) -> None:
        """Not used in Vector PrePlan ReAct workflow."""
        pass

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate vector retrieval and planning capabilities with a graph.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional arguments
        """
        # This method could be implemented to modify existing graphs with these capabilities
        pass

    async def retrieve_from_vector_store(self, query: str, **kwargs) -> List[Document]:
        """Retrieve relevant documents from multiple vector stores.

        Args:
            query: The query to search for
            **kwargs: Additional arguments

        Returns:
            List of retrieved documents
        """
        try:
            all_documents = []
            limit_per_collection = kwargs.get(
                "limit", 4
            )  # Get 4 results from each collection

            # Query each collection and gather results
            for collection_name in self.collection_names:
                try:
                    # Query vectors using the backend
                    vector_results = await backend.query_vectors(
                        collection_name=collection_name,
                        query_text=query,
                        limit=limit_per_collection,
                        embeddings=self.embeddings,
                    )

                    # Convert to LangChain Documents and add collection source
                    documents = [
                        Document(
                            page_content=doc.get("page_content", ""),
                            metadata={
                                **doc.get("metadata", {}),
                                "collection_source": collection_name,
                            },
                        )
                        for doc in vector_results
                    ]

                    all_documents.extend(documents)
                    logger.info(
                        f"Retrieved {len(documents)} documents from collection {collection_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to retrieve from collection {collection_name}: {str(e)}"
                    )
                    continue  # Continue with other collections if one fails

            logger.info(
                f"Retrieved total of {len(all_documents)} documents from all collections"
            )
            return all_documents
        except Exception as e:
            logger.error(f"Vector store retrieval failed: {str(e)}")
            return []

    async def create_plan(
        self, query: str, context_docs: List[Document] = None, **kwargs
    ) -> str:
        """Create a plan based on the user's query and vector retrieval results.

        Args:
            query: The user's query
            context_docs: Optional retrieved context documents
            **kwargs: Additional arguments

        Returns:
            Generated plan
        """
        # Create a more decisive planning prompt with context
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

        # Add vector context to the planning prompt if available
        if context_docs:
            context_str = "\n\n".join([doc.page_content for doc in context_docs])
            planning_prompt += f"\n\nHere is additional context that may be helpful:\n\n{context_str}\n\nUse this context to inform your plan."

        # Add available tools to the planning prompt if available
        if hasattr(self, "tool_names") and self.tool_names:
            tool_info = "\n\nTools available to you:\n"
            for tool_name in self.tool_names:
                tool_info += f"- {tool_name}\n"
            planning_prompt += tool_info

        # Add tool descriptions if available
        if hasattr(self, "tool_descriptions") and self.tool_descriptions:
            planning_prompt += self.tool_descriptions

        # Create planning messages, including persona if available
        planning_messages = []

        # If we're in the service context and persona is available, add it as a system message
        if hasattr(self, "persona") and self.persona:
            planning_messages.append(SystemMessage(content=self.persona))

        # Add the planning prompt
        planning_messages.append(HumanMessage(content=planning_prompt))

        try:
            logger.info(
                "Creating thought process notes for user query with vector context"
            )

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

            logger.info(
                "Thought process notes created successfully with vector context"
            )
            logger.debug(f"Notes content length: {len(plan)}")

            # Use the process_step method to emit the plan with a planning status
            await self.callback_handler.process_step(
                content=plan, role="assistant", thought="Planning Phase with Context"
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
        """Create the Vector PrePlan ReAct workflow graph."""
        logger.info("Creating Vector PrePlan ReAct workflow graph")
        tool_node = ToolNode(self.tools)
        logger.debug(f"Created tool node with {len(self.tools)} tools")

        def should_continue(state: ChatState) -> str:
            messages = state["messages"]
            last_message = messages[-1]
            result = "tools" if last_message.tool_calls else END
            logger.debug(f"Continue decision: {result}")
            return result

        async def retrieve_context(state: ChatState) -> Dict:
            """Retrieve context from both vector store and web search."""
            messages = state["messages"]
            last_user_message = None
            for message in reversed(messages):
                if isinstance(message, HumanMessage):
                    last_user_message = message.content
                    break

            if not last_user_message:
                logger.warning("No user message found for context retrieval")
                return {"vector_results": [], "web_search_results": []}

            # Get vector results
            vector_results = await self.retrieve_from_vector_store(
                query=last_user_message
            )
            logger.info(f"Retrieved {len(vector_results)} documents from vector store")

            # Get web search results
            try:
                web_results = await self.web_search(last_user_message)
                logger.info(f"Retrieved {len(web_results)} web search results")
            except Exception as e:
                logger.error(f"Web search failed: {str(e)}")
                web_results = []

            return {"vector_results": vector_results, "web_search_results": web_results}

        def call_model_with_context_and_plan(state: ChatState) -> Dict:
            """Call model with context, plan, and web search results."""
            messages = state["messages"]
            vector_results = state.get("vector_results", [])
            web_results = state.get("web_search_results", [])
            plan = state.get("plan")

            # Add vector context to the system message if available
            if vector_results:
                context_str = "\n\n".join([doc.page_content for doc in vector_results])
                context_message = SystemMessage(
                    content=f"Here is additional context that may be helpful:\n\n{context_str}\n\n"
                    "Use this context to inform your response if relevant."
                )
                messages = [context_message] + messages

            # Add web search results if available
            if web_results:
                # Flatten web_results if it is a list of lists
                if any(isinstance(r, list) for r in web_results):
                    # Only flatten one level
                    flat_results = []
                    for r in web_results:
                        if isinstance(r, list):
                            flat_results.extend(r)
                        else:
                            flat_results.append(r)
                    web_results = flat_results

                web_context_chunks = []
                for i, result in enumerate(web_results):
                    if not isinstance(result, dict):
                        logger.warning(
                            f"Web search result at index {i} is not a dict: {type(result)}. Skipping."
                        )
                        continue
                    page_content = result.get("page_content")
                    metadata = result.get("metadata", {})
                    source_urls = metadata.get("source_urls", ["Unknown"])
                    if not isinstance(source_urls, list):
                        source_urls = [str(source_urls)]
                    if page_content is None:
                        logger.warning(
                            f"Web search result at index {i} missing 'page_content'. Skipping."
                        )
                        continue
                    web_context_chunks.append(
                        f"Web Search Result {i+1}:\n{page_content}\nSource: {source_urls[0]}"
                    )
                web_context = "\n\n".join(web_context_chunks)
                if web_context:
                    web_message = SystemMessage(
                        content=f"Here are relevant web search results:\n\n{web_context}\n\n"
                        "Consider this information in your response if relevant."
                    )
                    messages = [web_message] + messages

            # Add the plan as a system message if it exists and hasn't been added yet
            if plan is not None and not any(
                isinstance(msg, SystemMessage) and "thought" in msg.content.lower()
                for msg in messages
            ):
                logger.info("Adding thought notes to messages as system message")
                plan_message = SystemMessage(
                    content=f"""
                    Follow these decisive actions to address the user's query:
                    
                    {plan}
                    
                    Execute these steps directly without asking for confirmation.
                    Be decisive and action-oriented in your responses.
                    """
                )
                messages = [plan_message] + messages

            # If decisive behavior is enabled and there's no plan-related system message,
            # add a decisive behavior system message
            elif getattr(self, "decisive_behavior", False) and not any(
                isinstance(msg, SystemMessage) for msg in messages
            ):
                logger.info("Adding decisive behavior instruction as system message")
                decisive_message = SystemMessage(
                    content="Be decisive and take action without asking for confirmation. "
                    "When the user requests something, proceed directly with executing it."
                )
                messages = [decisive_message] + messages

            logger.debug(
                f"Calling model with {len(messages)} messages, "
                f"{len(vector_results)} vector results, "
                f"{len(web_results)} web results, and "
                f"{'a plan' if plan else 'no plan'}"
            )

            response = self.llm.invoke(messages)
            return {"messages": [response]}

        workflow = StateGraph(ChatState)

        # Add nodes
        workflow.add_node("context_retrieval", retrieve_context)
        workflow.add_node("agent", call_model_with_context_and_plan)
        workflow.add_node("tools", tool_node)

        # Set up the execution flow
        workflow.add_edge(START, "context_retrieval")
        workflow.add_edge("context_retrieval", "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        logger.info("Vector PrePlan graph setup complete")
        return workflow


class ChatService:
    """Service for executing Chat LangGraph operations."""

    def __init__(
        self,
        collection_names: Union[str, List[str]],
        embeddings: Optional[Embeddings] = None,
    ):

        self.collection_names = collection_names
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.message_processor = MessageProcessor()

    def setup_callback_handler(self, queue, loop):
        from services.workflows.workflow_service import BaseWorkflowService

        return BaseWorkflowService.create_callback_handler(queue, loop)

    async def stream_task_results(self, task, queue):
        from services.workflows.workflow_service import BaseWorkflowService

        async for chunk in BaseWorkflowService.stream_results_from_task(
            task=task, callback_queue=queue, logger_name=self.__class__.__name__
        ):
            yield chunk

    async def _execute_stream_impl(
        self,
        messages: List[Union[SystemMessage, HumanMessage, AIMessage]],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        try:
            from services.workflows.workflow_service import WorkflowBuilder

            callback_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            callback_handler = self.setup_callback_handler(callback_queue, loop)
            workflow = (
                WorkflowBuilder(ChatWorkflow)
                .with_callback_handler(callback_handler)
                .with_tools(list(tools_map.values()) if tools_map else [])
                .build(
                    collection_names=self.collection_names,
                    embeddings=self.embeddings,
                )
            )
            if persona:
                decisive_guidance = "\n\nBe decisive and take action without asking for confirmation. When the user requests something, proceed directly with executing it rather than asking if they want you to do it."
                workflow.persona = persona + decisive_guidance
            if tools_map:
                workflow.tool_names = list(tools_map.keys())
                tool_descriptions = "\n\nTOOL DESCRIPTIONS:\n"
                for name, tool in tools_map.items():
                    description = getattr(
                        tool, "description", "No description available"
                    )
                    tool_descriptions += f"- {name}: {description}\n"
                workflow.tool_descriptions = tool_descriptions
            logger.info(
                f"Retrieving documents from vector store for query: {input_str[:50]}..."
            )
            documents = await workflow.retrieve_from_vector_store(query=input_str)
            logger.info(f"Retrieved {len(documents)} documents from vector store")
            try:
                logger.info("Creating plan with vector context...")
                plan = await workflow.create_plan(input_str, context_docs=documents)
                logger.info(f"Plan created successfully with {len(plan)} characters")
            except Exception as e:
                logger.error(f"Planning failed, continuing with execution: {str(e)}")
                yield {
                    "type": "token",
                    "content": "Proceeding directly to answer...\n\n",
                }
                plan = None
            graph = workflow._create_graph()
            runnable = graph.compile()
            logger.info("Graph compiled successfully")
            config = {"callbacks": [callback_handler]}
            task = asyncio.create_task(
                runnable.ainvoke(
                    {"messages": messages, "vector_results": documents, "plan": plan},
                    config=config,
                )
            )
            async for chunk in self.stream_task_results(task, callback_queue):
                yield chunk
        except Exception as e:
            logger.error(f"Failed to execute Chat stream: {str(e)}", exc_info=True)
            raise ExecutionError(f"Chat stream execution failed: {str(e)}")

    async def execute_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        filtered_content = self.message_processor.extract_filtered_content(history)
        messages = self.message_processor.convert_to_langchain_messages(
            filtered_content, input_str, persona
        )
        async for chunk in self._execute_stream_impl(
            messages=messages,
            input_str=input_str,
            persona=persona,
            tools_map=tools_map,
            **kwargs,
        ):
            yield chunk


# Facade function
async def execute_chat_stream(
    collection_names: Union[str, List[str]],
    history: List[Dict],
    input_str: str,
    persona: Optional[str] = None,
    tools_map: Optional[Dict] = None,
    embeddings: Optional[Embeddings] = None,
) -> AsyncGenerator[Dict, None]:
    """Execute a Chat stream.

    This workflow combines vector retrieval and planning:
    1. Retrieves relevant context from multiple vector stores
    2. Creates a plan based on the user's query and retrieved context
    3. Executes the ReAct workflow with both context and plan
    """
    embeddings = embeddings or OpenAIEmbeddings()
    service = ChatService(
        collection_names=collection_names,
        embeddings=embeddings,
    )
    async for chunk in service.execute_stream(history, input_str, persona, tools_map):
        yield chunk
