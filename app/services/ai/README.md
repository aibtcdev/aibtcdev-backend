# ai Folder Documentation

## Overview
This folder orchestrates AI-related services, including embeddings and simple workflows for tasks like evaluation and recommendation. It leverages LLM integrations and embedding models for intelligent processing.

## Key Components
- **Files**:
  - __init__.py: Initialization file for the package.

- **Subfolders**:
  - embeddings/: Text embedding services. [embeddings README](./embeddings/README.md) - Embedding generation.
  - simple_workflows/: AI workflow orchestration. [simple_workflows README](./simple_workflows/README.md) - Workflow management.

## Relationships and Integration
AI services are used in job tasks like dao_proposal_evaluation.py (app/services/infrastructure/job_management/tasks/) and integrate with prompts and processors in simple_workflows/. Depend on app/lib/tokenizer.py for token management.

## Navigation
- **Parent Folder**: [Up: services Folder README](../README.md)
- **Child Folders** (if applicable): 
  - [Down: embeddings README](./embeddings/README.md)
  - [Down: simple_workflows README](./simple_workflows/README.md)

## Additional Notes
Configure AI provider keys in app/config.py; monitor usage costs.
