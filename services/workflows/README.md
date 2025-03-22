# Workflow Architecture

This module provides a framework for creating and executing LangGraph-based workflows using LangChain and OpenAI.

## Architecture Overview

The workflow architecture is organized into several layers:

1. **Base Components**: Core abstractions and interfaces
2. **Service Layer**: Standardized execution and streaming
3. **Workflow Implementations**: Concrete workflow types
4. **Special Purpose Workflows**: Domain-specific implementations

## 1. Base Components

### BaseWorkflow

The foundation for all workflow implementations. It provides:
- Common initialization logic
- Validation framework
- Graph execution patterns

```python
workflow = BaseWorkflow()
result = await workflow.execute(initial_state)
```

### Capability Mixins

Capabilities that can be mixed into workflows:

- `PlanningCapability`: Adds planning before execution
- `VectorRetrievalCapability`: Adds vector database retrieval

```python
class MyWorkflow(BaseWorkflow, PlanningCapability, VectorRetrievalCapability):
    # Implementation that can use both capabilities
```

## 2. Service Layer

### WorkflowService

Interface for service implementations that provide a standard execution method:

```python
# Standard interface
async for chunk in service.execute_stream(
    history=history, 
    input_str=input_str, 
    tools_map=tools_map
):
    # Process streaming chunks
```

### WorkflowFactory and Builder

Factory pattern for creating workflow instances:

```python
# Create a workflow service using the factory
service = WorkflowFactory.create_workflow_service(
    workflow_type="vector",
    vector_collection="my_collection"
)

# Build a workflow instance with the builder
workflow = (
    WorkflowBuilder(ReactWorkflow)
    .with_callback_handler(callback_handler)
    .with_tools(tools)
    .build()
)
```

## 3. Core Workflow Implementations

### ReactWorkflow

Basic reasoning + action workflow using the ReAct pattern.

### VectorReactWorkflow

ReAct workflow with vector store integration for context retrieval.

### PreplanReactWorkflow

ReAct workflow with planning before execution.

### VectorPreplanReactWorkflow

ReAct workflow that combines vector retrieval and planning:
1. Retrieves relevant context from vector storage based on the user query
2. Creates a plan using both the query and retrieved context
3. Executes the workflow with both context and plan

This workflow is ideal for complex tasks that benefit from both:
- External knowledge from vector storage
- Strategic planning before execution

## 4. Special Purpose Workflows

Domain-specific implementations:

- `ProposalEvaluationWorkflow`: Evaluates DAO proposals
- `TweetAnalysisWorkflow`: Analyzes tweets for DAO actions
- `TweetGeneratorWorkflow`: Generates tweets about DAOs

## Usage Examples

### Basic ReAct Workflow

```python
from services.workflows import execute_workflow_stream

async for chunk in execute_workflow_stream(
    workflow_type="react",
    history=conversation_history,
    input_str="What is the current price of Bitcoin?",
    tools_map={"price_check": price_check_tool}
):
    yield chunk
```

### Vector Retrieval Workflow

```python
from services.workflows import execute_workflow_stream

async for chunk in execute_workflow_stream(
    workflow_type="vector",
    history=conversation_history,
    input_str="Tell me about DAO governance",
    vector_collections="dao_docs",
    tools_map=dao_tools
):
    yield chunk
```

### Planning Workflow

```python
from services.workflows import execute_workflow_stream

async for chunk in execute_workflow_stream(
    workflow_type="preplan",
    history=conversation_history,
    input_str="Create a proposal for the treasury",
    tools_map=proposal_tools
):
    yield chunk
```

### Vector PrePlan Workflow

```python
from services.workflows import execute_workflow_stream

async for chunk in execute_workflow_stream(
    workflow_type="vector_preplan",
    history=conversation_history,
    input_str="Create a proposal for the treasury using past proposals as references",
    vector_collections=["dao_docs", "knowledge_collection"],
    tools_map=proposal_tools
):
    yield chunk
```

## Creating New Workflows

To create a new workflow:

1. Define a state type (TypedDict)
2. Create a workflow class extending BaseWorkflow and any capability mixins
3. Implement `_create_graph()` and any required methods
4. Create a service class extending BaseWorkflowService
5. Implement `_execute_stream_impl()`
6. Add to factory mapping if needed

Example:

```python
# 1. Define state
class MyState(TypedDict):
    messages: Annotated[list, add_messages]
    custom_data: str

# 2. Create workflow class
class MyWorkflow(BaseWorkflow[MyState], PlanningCapability):
    def _create_graph(self) -> StateGraph:
        # Implement graph creation
        ...

# 3. Create service class
class MyService(BaseWorkflowService):
    async def _execute_stream_impl(self, messages, input_str, **kwargs):
        # Implement execution
        ...

# 4. Add to factory
WorkflowFactory.create_workflow_service.service_map["my_workflow"] = MyService
``` 