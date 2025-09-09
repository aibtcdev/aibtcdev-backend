# prompts Folder Documentation

## Overview
This folder manages prompt templates and loading utilities for AI-driven workflows, particularly in proposal evaluation, metadata generation, and recommendations. It uses string templates and a loader class to dynamically prepare prompts for LLM interactions, leveraging patterns like system/user prompt separation and template formatting.

## Key Components
- **Files**:
  - [evaluation.py](evaluation.py): Defines evaluation system prompts and user templates for assessing DAO proposals.
  - [__init__.py](__init__.py): Initialization file for the package.
  - [loader.py](loader.py): Contains the PromptLoader class for loading and managing prompt types dynamically.
  - [metadata.py](metadata.py): Provides metadata system prompts and templates for generating proposal titles, descriptions, and images.
  - [recommendation.py](recommendation.py): Defines recommendation system prompts and templates for generating DAO improvement suggestions.

- **Subfolders**:
  - (None)

## Relationships and Integration
Prompts here are loaded via the PromptLoader in loader.py and used in parent folder files like evaluation.py, metadata.py, and recommendation.py for AI orchestration. They depend on models from app/services/ai/simple_workflows/models.py for output structures and integrate with LLM calls in llm.py.

## Navigation
- **Parent Folder**: [Up: simple_workflows Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Prompts are designed to be extensible; new types can be added by registering them in the loader. Test templates with sample data to ensure compatibility with token limits.
