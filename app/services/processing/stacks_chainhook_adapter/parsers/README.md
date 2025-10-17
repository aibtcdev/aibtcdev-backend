# parsers Folder Documentation

## Overview
This folder contains parsers for Chainhook data, focusing on Clarity repr formats in events. It uses abstract base classes for extensibility. Key technologies include regex for pattern matching and recursive parsing.

## Key Components
- **Files**:
  - base.py: Abstract base parser class.
  - clarity.py: Parser for Clarity repr strings in events.
  - __init__.py: Initialization file for the package.

- **Subfolders**:
  - (None)

## Relationships and Integration
Parsers are registered in ../adapters/chainhook_adapter.py and used for event value parsing. Depend on ../models/chainhook.py for data structures.

## Navigation
- **Parent Folder**: [Up: stacks_chainhook_adapter Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Add new parsers by subclassing BaseParser; register in adapter for use.
