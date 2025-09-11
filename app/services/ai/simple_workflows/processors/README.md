# processors Folder Documentation

## Overview
This folder contains specialized processors for handling specific data types in AI workflows, such as airdrops, images, and Twitter content. It implements task-specific logic for data extraction, generation, and integration, using exception handling and async patterns for robust processing.

## Key Components
- **Files**:
  - [airdrop.py](airdrop.py): Processes airdrop-related data in workflows.
  - [images.py](images.py): Handles image generation and evaluation, including ImageGenerationError exceptions.
  - [__init__.py](__init__.py): Initialization file for the package.
  - [twitter.py](twitter.py): Manages Twitter (X) data processing, such as tweet retrieval and analysis.

- **Subfolders**:
  - (None)

## Relationships and Integration
Processors here are invoked by the orchestrator in the parent folder's orchestrator.py and tool_executor.py. They rely on utilities from app/lib/images.py and app/lib/utils.py for image and URL extraction, and output to models in app/services/ai/simple_workflows/models.py.

## Navigation
- **Parent Folder**: [Up: simple_workflows Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
These processors are modular; add new ones for additional data types as needed. Monitor for API rate limits in Twitter processing.
