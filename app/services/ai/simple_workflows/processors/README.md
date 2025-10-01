# processors Folder Documentation

## Overview
This folder contains specialized processors for handling attachments and data in AI workflows, including airdrop fetching/formatting, image generation, and tweet processing. It uses async functions for efficiency and integrates with backend models. Key technologies include async/await for concurrency and Pydantic for data validation.

## Key Components
- **Files**:
  - airdrop.py: Fetches and formats airdrop data from database for LLM analysis.
  - images.py: Processes image attachments in proposals using AI generation.
  - __init__.py: Initialization file for the package.
  - twitter.py: Handles tweet attachments by fetching and formatting tweet data.

- **Subfolders**:
  - (None)

## Relationships and Integration
Processors are called from app/services/ai/simple_workflows/evaluation.py and orchestrator.py to enrich proposal content. They depend on backend models from app/backend/models.py and utilities like app/lib/images.py for image handling.

## Navigation
- **Parent Folder**: [Up: simple_workflows Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Processors are designed to be extensible; add new ones for additional attachment types. Ensure async compatibility when integrating.
