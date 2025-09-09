# lib Folder Documentation

## Overview
This folder houses utility libraries for images, logging, API clients, persona generation, token assets, tokenization, tools, and general utils. It provides reusable functions and classes for application-wide support.

## Key Components
- **Files**:
  - [images.py](images.py): Image generation and error handling.
  - [__init__.py](__init__.py): Initialization file for the package.
  - [logger.py](logger.py): Logging configuration with JSON formatting.
  - [lunarcrush.py](lunarcrush.py): LunarCrush API client.
  - [persona.py](persona.py): Persona generation utilities.
  - [token_assets.py](token_assets.py): Token asset management.
  - [tokenizer.py](tokenizer.py): Token counting and trimming.
  - [tools.py](tools.py): Tool utilities.
  - [utils.py](utils.py): General utilities like URL extraction.

- **Subfolders**:
  - (None)

## Relationships and Integration
Utils are used across services (app/services/), tools (app/tools/), and AI workflows. For example, logger.py is used in middleware/.

## Navigation
- **Parent Folder**: [Up: app Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Keep utilities lightweight; refactor common code here.
