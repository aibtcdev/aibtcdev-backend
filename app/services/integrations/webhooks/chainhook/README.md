# chainhook Folder Documentation

## Overview
This folder manages Chainhook webhook handling, including parsing, service implementation, and event dispatching. It processes blockchain events using models and handlers, employing dataclass-based structures and service classes for webhook integration, with a focus on transaction and block-level event processing.

## Key Components
- **Files**:
  - [handler.py](handler.py): Likely coordinates handler instantiation and event routing.
  - [__init__.py](__init__.py): Initialization file for the package.
  - [models.py](models.py): Defines dataclass models like ChainTip for event data.
  - [parser.py](parser.py): Parses incoming Chainhook webhook payloads.
  - [service.py](service.py): Implements ChainhookService, extending a base WebhookService for event processing.

- **Subfolders**:
  - [handlers/](handlers/): Contains specific event handlers and utilities. [handlers README](./handlers/README.md) - Specialized handlers for various blockchain events.

## Relationships and Integration
This folder's service integrates with base webhook functionality from the parent folder's base.py and uses handlers from the subfolder to process events. It interacts with backend models (e.g., app/backend/models.py) for queuing messages and may trigger jobs in app/services/infrastructure/job_management/tasks/.

## Navigation
- **Parent Folder**: [Up: webhooks Folder README](../README.md)
- **Child Folders** (if applicable): 
  - [Down: handlers README](./handlers/README.md)

## Additional Notes
Ensure webhook payloads are validated in parser.py to handle varying blockchain event formats. Extensible via new handlers in the subfolder.
