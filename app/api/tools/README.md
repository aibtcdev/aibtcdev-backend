# tools Folder Documentation

## Overview
This folder defines API routers and models for various tools, including agent accounts, DAO operations, discovery, evaluation, and social integrations. It uses FastAPI APIRouter for endpoint definitions.

## Key Components
- **Files**:
  - agent_account.py: Tools for agent account management.
  - dao.py: DAO-related tools.
  - discovery.py: Discovery tools.
  - evaluation.py: Evaluation tools.
  - faktory.py: Faktory integration tools.
  - __init__.py: Initializes the router with prefix "/tools".
  - models.py: Defines models for tool APIs.
  - social.py: Social media tools.
  - wallet.py: Wallet management tools.

- **Subfolders**:
  - (None)

## Relationships and Integration
Routers here are mounted in app/api/__init__.py and use tools from app/tools/ for implementation. Depends on backend models (app/backend/models.py) and may trigger jobs or AI workflows.

## Navigation
- **Parent Folder**: [Up: api Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Endpoints are tagged "tools"; secure with dependencies from app/api/dependencies.py.
