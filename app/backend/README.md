# backend Folder Documentation

## Overview
This folder provides backend abstractions, models, and factory for data access, primarily using Supabase. It defines abstract base classes for operations and Pydantic models for data validation, supporting dynamic types and filters.

## Key Components
- **Files**:
  - abstract.py: AbstractBackend ABC with methods for data operations.
  - factory.py: Factory to get backend instances.
  - __init__.py: Initialization file for the package.
  - models.py: Pydantic models like QueueMessage, WalletFilter.
  - supabase.py: Supabase-specific backend implementation.

- **Subfolders**:
  - (None)

## Relationships and Integration
Backend is used throughout services (app/services/) and API (app/api/) for CRUD operations. Models align with database schemas in supabase/migrations/.

## Navigation
- **Parent Folder**: [Up: app Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Extend AbstractBackend for new storage backends; ensure model consistency with migrations.
