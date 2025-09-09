# hiro Folder Documentation

## Overview
This folder integrates with the Hiro API for blockchain data access, including models and utilities for chain state and webhook configurations. It uses dataclass models and API clients for querying blockchain information.

## Key Components
- **Files**:
  - base.py: Base classes for Hiro integrations.
  - hiro_api.py: Implements Hiro API client.
  - __init__.py: Initialization file for the package.
  - models.py: Defines models like ChainTip.
  - platform_api.py: Handles platform-specific API interactions.
  - utils.py: Utilities including WebhookConfig dataclass.

- **Subfolders**:
  - (None)

## Relationships and Integration
API clients here are used in monitoring tasks like chain_state_monitor.py in app/services/infrastructure/job_management/tasks/. Depends on config from app/config.py and may interact with backend for storing chain states.

## Navigation
- **Parent Folder**: [Up: integrations Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Configure API keys securely; monitor for rate limits in production.
