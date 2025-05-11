"""Hierarchical Agent Teams (HAT) workflow implementation.

This module provides the implementation for Hierarchical Agent Teams (HAT)
workflows where multiple specialized agents work together with a supervisor
coordinating their activities.
"""

from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
    get_type_hints,
)

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.channels.last_value import LastValue
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from lib.logger import configure_logger
from services.workflows.capability_mixins import (
    BaseCapabilityMixin,
    ComposableWorkflowMixin,
    StateType,
)


# Define merge functions for managing parallel state updates
def append_list_fn(key, values):
    """Append multiple list updates."""
    # Handle case where we're dealing with single strings or non-list values
    result = []
    for value in values:
        if isinstance(value, list):
            result.extend(value)
        else:
            result.append(value)
    return list(set(result))  # Deduplicate lists


def merge_dict_fn(key, values):
    """Merge multiple dictionary updates."""
    # Handle cases where we might get non-dict values
    result = {}
    for value in values:
        if isinstance(value, dict):
            result.update(value)
        elif value is not None:
            # Try to convert to dict if possible, otherwise use as a key
            try:
                result.update(dict(value))
            except (ValueError, TypeError):
                result[str(value)] = True
    return result  # Combine dictionaries


logger = configure_logger(__name__)


class SupervisorMixin(BaseCapabilityMixin):
    """Mixin for implementing supervisor functionality in HAT workflows.

    The supervisor is responsible for routing between agents and
    making decisions about workflow progression.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        routing_key: str = "next_step",
    ):
        """Initialize the supervisor mixin.

        Args:
            config: Configuration dictionary
            routing_key: Key in state to use for routing
        """
        super().__init__(config=config, state_key=routing_key)
        self.routing_key = routing_key
        self.routing_map = {}
        self.halt_condition = lambda state: False
        # Default routing function (should be replaced with set_routing_logic)
        self.routing_func = lambda state: "end"

    def set_routing_logic(self, routing_func: Callable) -> None:
        """Set the routing function to determine the next step.

        Args:
            routing_func: Function that takes the state and returns the next step
        """
        self.routing_func = routing_func

    def set_halt_condition(self, halt_func: Callable) -> None:
        """Set a condition that will halt the workflow.

        Args:
            halt_func: Function that takes the state and returns a boolean
        """
        self.halt_condition = halt_func

    def map_step_to_node(self, step_name: str, node_name: str) -> None:
        """Map a step name to a node name.

        Args:
            step_name: Name of the step in routing logic
            node_name: Name of the node in the graph
        """
        self.routing_map[step_name] = node_name

    def router(self, state: StateType) -> Union[str, List[str]]:
        """Route to the next node(s) based on the state.

        Returns either a string node name or a list of node names for parallel execution.
        """
        next_step = state[self.routing_key]
        if next_step == "end" or next_step == END:
            return END
        return next_step

    async def process(self, state: StateType) -> Dict[str, Any]:
        """Process the current state and determine the next step.

        Args:
            state: Current workflow state

        Returns:
            Dict with next step information
        """
        # Check if halt condition is met
        if self.halt_condition(state):
            return {"next_step": END, "reason": "halt_condition_met"}

        # Determine next step using routing logic
        next_step = self.routing_func(state)

        # Handle special case for END constant
        if next_step == "end":
            next_step = END

        # Map to node name if a mapping exists
        if isinstance(next_step, list):
            # For parallel execution, map each item in the list
            mapped_step = [self.routing_map.get(step, step) for step in next_step]
        else:
            mapped_step = self.routing_map.get(next_step, next_step)

        return {
            "next_step": mapped_step,
            "timestamp": state.get("timestamp", ""),
        }

    def add_to_graph(self, graph: StateGraph, **kwargs) -> None:
        """Add the supervisor to the graph.

        Args:
            graph: StateGraph to add node to
            **kwargs: Additional arguments
        """
        node_name = kwargs.get("node_name", "supervisor")

        async def supervisor_node(state: StateType) -> StateType:
            result = await self.process(state)
            next_step = result["next_step"]
            # Normalize "end" to END constant if needed
            if next_step == "end":
                next_step = END
            state[self.routing_key] = next_step
            return state

        graph.add_node(node_name, supervisor_node)

        # Define conditional edges from supervisor to other nodes
        def router(state: StateType) -> Union[str, List[str]]:
            next_step = state[self.routing_key]
            # Handle both string and list cases
            if isinstance(next_step, list):
                return next_step
            if next_step == "end" or next_step == END:
                return END
            return next_step

        # Create a complete routing map that includes END
        routing_map_with_end = {
            **{step: step for step in self.routing_map.values()},
            "end": END,
            END: END,
        }

        # Add explicit entry for every node we might want to route to
        for node in graph.nodes:
            if (
                node not in routing_map_with_end
                and node != "supervisor"
                and node != END
            ):
                routing_map_with_end[node] = node

        # Add conditional edges with the complete routing map
        graph.add_conditional_edges(node_name, router, routing_map_with_end)


class HierarchicalTeamWorkflow(ComposableWorkflowMixin):
    """Implementation of a Hierarchical Agent Team workflow.

    This workflow orchestrates a team of specialized agents coordinated
    by a supervisor to solve complex tasks.
    """

    def __init__(self, name: str = None, config: Optional[Dict[str, Any]] = None):
        """Initialize the hierarchical team workflow.

        Args:
            name: Name identifier for this workflow
            config: Configuration dictionary
        """
        super().__init__(name=name)
        self.config = config or {}
        self.supervisor = SupervisorMixin(config=self.config)
        self.entry_point = None

    def set_entry_point(self, node_name: str) -> None:
        """Set the entry point for the workflow.

        Args:
            node_name: Name of the starting node
        """
        self.entry_point = node_name

    def set_supervisor_logic(self, routing_func: Callable) -> None:
        """Set the routing logic for the supervisor.

        Args:
            routing_func: Function that determines the next step
        """
        self.supervisor.set_routing_logic(routing_func)

    def set_halt_condition(self, halt_func: Callable) -> None:
        """Set a condition that will halt the workflow.

        Args:
            halt_func: Function that takes the state and returns a boolean
        """
        self.supervisor.set_halt_condition(halt_func)

    def add_parallel_execution(
        self, from_node: str, to_nodes: List[str], merge_node: str
    ) -> None:
        """Add parallel execution paths to the workflow.

        Args:
            from_node: Node where parallel execution begins
            to_nodes: List of nodes to execute in parallel
            merge_node: Node where results are merged
        """
        self.parallel_executions = {
            "from_node": from_node,
            "to_nodes": to_nodes,
            "merge_node": merge_node,
        }

    def build_graph(self) -> StateGraph:
        """Build the hierarchical team workflow graph.

        Returns:
            StateGraph: The compiled workflow graph
        """
        if not self.entry_point:
            raise ValueError("Entry point must be set before building graph")

        # Create graph with the appropriate state type
        state_type = self.config.get("state_type", Dict[str, Any])

        # Create graph with minimum configuration
        graph = StateGraph(state_type)

        # Get recursion limit to prevent infinite loops (will be passed to compile())
        recursion_limit = self.config.get("recursion_limit", 10)
        self.logger.info(f"Setting recursion limit to {recursion_limit}")

        # Set up key-specific channels for concurrent updates
        if hasattr(state_type, "__annotations__"):
            type_hints = get_type_hints(state_type, include_extras=True)
            for key, annotation in type_hints.items():
                # Check if it's an Annotated type with a merge function
                if hasattr(annotation, "__metadata__") and callable(
                    annotation.__metadata__[-1]
                ):
                    merge_func = annotation.__metadata__[-1]
                    field_type = annotation.__origin__
                    # Use direct assignment of channels instead of config parameter
                    if key not in graph.channels:
                        if merge_func == append_list_fn:
                            channel = LastValue(field_type)
                            channel.reduce = merge_func
                            graph.channels[key] = channel
                        elif merge_func == merge_dict_fn:
                            channel = LastValue(field_type)
                            channel.reduce = merge_func
                            graph.channels[key] = channel

        # Add all sub-workflows to the graph
        for name, workflow in self.sub_workflows.items():
            try:
                workflow.add_to_graph(graph, node_name=name)
                # Map step name to node name in supervisor
                self.supervisor.map_step_to_node(name, name)
                self.logger.debug(f"Added sub-workflow node: {name}")
            except Exception as e:
                self.logger.error(
                    f"Error adding sub-workflow {name}: {str(e)}", exc_info=True
                )
                raise ValueError(f"Failed to add sub-workflow {name}: {str(e)}")

        # Add supervisor to graph
        try:
            self.supervisor.add_to_graph(graph)
            self.logger.debug("Added supervisor node")
        except Exception as e:
            self.logger.error(f"Error adding supervisor: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to add supervisor: {str(e)}")

        # Set entry point
        graph.set_entry_point(self.entry_point)
        self.logger.debug(f"Set entry point to {self.entry_point}")

        # Connect entry point to supervisor
        graph.add_edge(self.entry_point, "supervisor")
        self.logger.debug(f"Added edge: {self.entry_point} -> supervisor")

        # Add edges from all nodes to supervisor
        for name in self.sub_workflows.keys():
            if name != self.entry_point:
                graph.add_edge(name, "supervisor")
                self.logger.debug(f"Added edge: {name} -> supervisor")

        # Add parallel execution if configured
        if hasattr(self, "parallel_executions"):
            pe = self.parallel_executions

            # Define function for parallel branching
            def branch_function(state: StateType) -> Dict:
                """Branch to parallel nodes or return to supervisor based on state.

                This returns both the next nodes and any state updates needed.
                """
                # For debugging, log the state keys we care about
                self.logger.debug(
                    f"Branch function evaluating state: "
                    f"historical_score={state.get('historical_score') is not None}, "
                    f"financial_score={state.get('financial_score') is not None}, "
                    f"social_score={state.get('social_score') is not None}, "
                    f"in_parallel={state.get('in_parallel_execution', False)}"
                )

                # Check if we're already in parallel execution
                if state.get("in_parallel_execution", False):
                    # Check if all parallel executions have completed
                    all_completed = True
                    for node_name in pe["to_nodes"]:
                        score_key = f"{node_name.replace('_agent', '')}_score"
                        if state.get(score_key) is None:
                            all_completed = False
                            break

                    if all_completed:
                        self.logger.debug(
                            f"All parallel nodes complete, routing to {pe['merge_node']}"
                        )
                        # Return to merge node and clear the in_parallel_execution flag
                        return {
                            "nodes": [pe["merge_node"]],
                            "state_updates": {"in_parallel_execution": False},
                        }
                    else:
                        # Still waiting for some parallel nodes to complete, let supervisor route
                        self.logger.debug(
                            "Some parallel nodes still executing, continuing parallel processing"
                        )
                        # Force parallel execution to stay on
                        return {
                            "nodes": ["supervisor"],
                            "state_updates": {"in_parallel_execution": True},
                        }

                # When historical_score is set but financial_score and social_score are not,
                # we need to branch to both financial_agent and social_agent in parallel
                elif state.get("historical_score") is not None and all(
                    state.get(f"{node_name.replace('_agent', '')}_score") is None
                    for node_name in pe["to_nodes"]
                ):
                    self.logger.debug(
                        f"Starting parallel execution, branching to nodes: {pe['to_nodes']}"
                    )
                    # Set the in_parallel_execution flag to True
                    return {
                        "nodes": pe["to_nodes"],
                        "state_updates": {"in_parallel_execution": True},
                    }

                # Default case, return to supervisor for normal routing
                # Make sure we're not stuck in a loop
                self.logger.debug("Not branching, returning to supervisor")

                # We need to ensure that if historical_score exists but financial/social are missing,
                # we maintain the parallel execution flag (this fixes the looping problem)
                if state.get("historical_score") is not None and any(
                    state.get(f"{node_name.replace('_agent', '')}_score") is None
                    for node_name in pe["to_nodes"]
                ):
                    return {
                        "nodes": ["supervisor"],
                        "state_updates": {"in_parallel_execution": True},
                    }

                return {"nodes": ["supervisor"], "state_updates": {}}

            # For each parallel node, map it in the supervisor
            for node in pe["to_nodes"]:
                self.supervisor.map_step_to_node(node, node)

            # Add branching from source node
            # We need to wrap our branch_function to handle state updates
            def branch_wrapper(state: StateType) -> List[str]:
                result = branch_function(state)
                # Apply any state updates
                for key, value in result.get("state_updates", {}).items():
                    state[key] = value
                # Return the nodes to route to
                return result.get("nodes", ["supervisor"])

            # Create a mapping for all possible nodes, including supervisor and END
            branch_map = {node: node for node in pe["to_nodes"]}
            branch_map["supervisor"] = "supervisor"
            branch_map[pe["merge_node"]] = pe["merge_node"]
            # Explicitly map END constant
            branch_map[END] = END  # Ensure END is correctly mapped

            # Add branching from source node using our wrapper
            graph.add_conditional_edges(pe["from_node"], branch_wrapper, branch_map)
            self.logger.debug(
                f"Added conditional edges for parallel execution from {pe['from_node']}"
            )

            # Connect merge node to supervisor
            graph.add_edge(pe["merge_node"], "supervisor")
            self.logger.debug(f"Added edge: {pe['merge_node']} -> supervisor")
        else:
            # Even without explicit parallel execution, we need to make sure
            # the supervisor can handle returning lists of nodes for parallel execution
            self.logger.debug(
                "No parallel execution configured, relying on supervisor for parallel routing"
            )

        # Compile the graph with the recursion limit configuration
        compiled_graph = graph.compile(
            name="HierarchicalTeamWorkflow",
            checkpointer=None,
            debug=self.config.get("debug", False),
        )

        # Pass recursion limit through with_config
        compiled_graph = compiled_graph.with_config(
            {"recursion_limit": recursion_limit}
        )

        self.logger.info("Compiled hierarchical team workflow graph")

        # Return the compiled graph
        return compiled_graph
