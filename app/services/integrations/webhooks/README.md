# webhooks Folder Documentation

## Overview
This folder provides base classes and services for webhook integrations, handling incoming webhooks from various sources like Chainhook and DAO events. It defines abstract base classes for webhook services and includes parsing utilities, using async patterns for event processing.

## Key Components
- **Files**:
  - [base.py](base.py): Defines base WebhookService and related abstractions.
  - [__init__.py](__init__.py): Initialization file for the package.

- **Subfolders**:
  - [chainhook/](chainhook/): Manages Chainhook-specific webhook handling. [chainhook README](./chainhook/README.md) - Chainhook event processing.
  - [dao/](dao/): Handles DAO webhook parsing. [dao README](./dao/README.md) - DAO event management.

## Relationships and Integration
Base classes here are extended in subfolders like chainhook/service.py and dao/service.py. Integrates with infrastructure jobs in app/services/infrastructure/job_management/ for event-triggered tasks and uses models from app/backend/models.py for data persistence.

## Navigation
- **Parent Folder**: [Up: integrations Folder README](../README.md)
- **Child Folders** (if applicable): 
  - [Down: chainhook README](./chainhook/README.md)
  - [Down: dao README](./dao/README.md)

## Additional Notes
Extend by adding new subfolders for additional webhook sources. Ensure secure validation of incoming payloads.
