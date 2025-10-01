# adapters Folder Documentation

## Overview
This folder contains adapter classes for transforming Stacks API data into Chainhook format, ensuring compatibility with existing handlers. It uses abstract base classes for extensibility. Key technologies include async methods and dataclasses for data handling.

## Key Components
- **Files**:
  - base.py: Abstract base adapter with transformation methods.
  - chainhook_adapter.py: Main adapter implementation for Stacks to Chainhook conversion.
  - __init__.py: Initialization file for the package.

- **Subfolders**:
  - (None)

## Relationships and Integration
Adapters use models from ../models/ and utilities from ../utils/. Integrated in app/services/processing/stacks_chainhook_adapter/__init__.py for block fetching.

## Navigation
- **Parent Folder**: [Up: stacks_chainhook_adapter Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Extend BaseAdapter for new transformations; ensure async compatibility.
