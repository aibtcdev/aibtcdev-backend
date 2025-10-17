# simple_workflows Folder Documentation

## Overview
This folder orchestrates simplified AI workflows for tasks like proposal evaluation, metadata generation, and recommendations. It uses LLM integrations, prompt management, and tool execution for structured AI processing, employing async patterns and Pydantic models for output validation.

## Key Components
- **Files**:
  - [evaluation.py](evaluation.py): Implements proposal evaluation workflows using prompts.
  - [__init__.py](__init__.py): Initialization file for the package.
  - [llm.py](llm.py): Handles LLM interactions and chat completions.
  - [metadata.py](metadata.py): Generates proposal metadata like titles and descriptions.
  - [models.py](models.py): Defines Pydantic models for outputs (e.g., AgentOutput, FinalOutput).
  - [orchestrator.py](orchestrator.py): Coordinates workflow execution.
  - [recommendation.py](recommendation.py): Generates DAO recommendations.
  - [streaming.py](streaming.py): Manages streaming responses for AI workflows.
  - [tool_executor.py](tool_executor.py): Executes tools directly in workflows.

- **Subfolders**:
  - [prompts/](prompts/): Manages prompt templates and loaders. [prompts README](./prompts/README.md) - Prompt loading and templates.
  - [processors/](processors/): Specialized data processors. [processors README](./processors/README.md) - Processors for images, Twitter, etc.

## Relationships and Integration
Workflows here use prompts from the prompts subfolder and processors from the processors subfolder, integrating with embedding services in app/services/ai/embeddings/. Outputs feed into backend models (app/backend/models.py) and may be used in API endpoints or job tasks.

## Navigation
- **Parent Folder**: [Up: ai Folder README](../README.md)
- **Child Folders** (if applicable): 
  - [Down: prompts README](./prompts/README.md)
  - [Down: processors README](./processors/README.md)

## Additional Notes
Workflows are modular; extend by adding new processors or prompts. Monitor LLM token usage via app/lib/tokenizer.py.
