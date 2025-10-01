# chainhook Folder Documentation

## Overview
This folder handles Chainhook webhook processing, including parsing, modeling, and servicing blockchain events. It uses dataclasses for data structures and async methods for efficiency. Key technologies include Pydantic-like validation via dataclasses and integration with webhook base classes.

## Key Components
- **Files**:
  - handler.py: Coordinates event handlers for Chainhook payloads.
  - __init__.py: Initialization file for the package.
  - models.py: Defines Chainhook data models like ChainHookData and TransactionWithReceipt.
  - parser.py: Parses incoming Chainhook webhook payloads.
  - service.py: Main service for processing Chainhook webhooks.

- **Subfolders**:
  - handlers/: Specialized event handlers (see [handlers README](./handlers/README.md)).

## Relationships and Integration
This folder extends WebhookService from app/services/integrations/webhooks/base.py. Models are used in handlers/ subfolder for event processing, integrating with app/backend/models.py for database operations.

## Navigation
- **Parent Folder**: [Up: webhooks Folder README](../README.md)
- **Child Folders** (if applicable): 
  - [handlers README](./handlers/README.md)

## Additional Notes
Ensure webhook payloads match expected models; extend parsers for new event types.
