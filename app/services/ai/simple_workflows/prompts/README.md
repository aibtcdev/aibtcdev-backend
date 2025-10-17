# prompts Folder Documentation

## Overview
This folder contains prompt templates and utilities for AI workflows in the simple_workflows system. It includes specialized prompts for proposal evaluation (general and ELONBTC-specific), metadata generation, and recommendation creation, along with a dynamic loader for managing prompts. Key technologies include Python string constants for prompts and dynamic module importing for extensibility.

## Key Components
- **Files**:
  - evaluation_elonbtc.py: Defines ELONBTC-specific evaluation prompts with monarch alignment focus.
  - evaluation.py: Contains general proposal evaluation prompts and templates.
  - __init__.py: Initialization file for the package.
  - loader.py: Utility for dynamically loading and managing prompt modules.
  - metadata.py: Prompts for generating proposal metadata like titles and summaries.
  - recommendation.py: Prompts for generating DAO improvement recommendations.

- **Subfolders**:
  - (None)

## Relationships and Integration
Prompts from this folder are loaded via loader.py and used in app/services/ai/simple_workflows/orchestrator.py for AI evaluations. They integrate with models from app/services/ai/simple_workflows/models.py for structured outputs and are called from tasks like dao_proposal_evaluation.py in app/services/infrastructure/job_management/tasks/.

## Navigation
- **Parent Folder**: [Up: simple_workflows Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Extend by adding new prompt modules following the naming convention (e.g., new_type.py with UPPERCASE_PROMPT constants). Use get_available_prompt_types() for discovery.
