# api Folder Documentation

## Overview
This folder defines FastAPI routers and endpoints for agents, DAOs, profiles, tools, and webhooks. It includes dependencies and initialization for API routing.

## Key Components
- **Files**:
  - agents.py: Agent endpoints.
  - daos.py: DAO endpoints.
  - dependencies.py: API dependencies.
  - __init__.py: Router initialization.
  - profiles.py: Profile endpoints.
  - webhooks.py: Webhook endpoints.

- **Subfolders**:
  - tools/: Tool-specific routers. [tools README](./tools/README.md) - Tool APIs.

## Relationships and Integration
Routers use services (app/services/) and backend (app/backend/) for logic. Mounted in app/main.py.

## Navigation
- **Parent Folder**: [Up: app Folder README](../README.md)
- **Child Folders** (if applicable): 
  - [Down: tools README](./tools/README.md)

## Additional Notes
Secure endpoints with dependencies; tag for OpenAPI docs.
