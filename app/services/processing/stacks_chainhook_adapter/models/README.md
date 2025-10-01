# models Folder Documentation

## Overview
This folder defines data models for Chainhook and Stacks API responses using dataclasses. It ensures structural compatibility between formats. Key technologies include Python dataclasses for lightweight, typed models.

## Key Components
- **Files**:
  - chainhook.py: Models for Chainhook format like ChainHookData and TransactionWithReceipt.
  - __init__.py: Initialization file for the package.
  - stacks.py: Models for Stacks API data like StacksBlock and StacksTransaction.

- **Subfolders**:
  - (None)

## Relationships and Integration
Models are used in ../adapters/ for transformations and ../parsers/ for data parsing. Chainhook models match webhook payloads for handler compatibility.

## Navigation
- **Parent Folder**: [Up: stacks_chainhook_adapter Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Keep models in sync with API changes; use asdict() for serialization.
