# utils Folder Documentation

## Overview
This folder provides utility functions for the Chainhook adapter, including helpers, output management, and template-based generation. It ensures compatibility with original Chainhook formats. Key technologies include regex, JSON handling, and dynamic templating.

## Key Components
- **Files**:
  - helpers.py: General utilities like address validation and amount parsing.
  - __init__.py: Initialization file for the package.
  - output_manager.py: Manages saving and summarizing adapter outputs.
  - template_manager.py: Generates Chainhook data using real templates.

- **Subfolders**:
  - (None)

## Relationships and Integration
Utilities support ../adapters/chainhook_adapter.py for data processing and output. Template manager uses chainhook-data/ files for accuracy.

## Navigation
- **Parent Folder**: [Up: stacks_chainhook_adapter Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Update templates in chainhook-data/ for new event types; use output_manager for debugging.
