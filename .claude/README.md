# .claude Folder Documentation

## Overview
This hidden folder contains configuration for Claude Code hooks, automating linting and formatting for Python files using tools like ruff and typos. It integrates with development workflows for code quality enforcement.

## Key Components
- **Files**:
  - hooks.json: Main configuration for various hooks (user-prompt-submit, file-edit, tool-use, pre-commit).
  - ruff-hooks.json: Simplified ruff-specific hook configuration.
  - README.md: This documentation file.

- **Subfolders**:
  - (None)

## Relationships and Integration
Hooks reference commands that run on files in app/ and other Python code, integrating with the development process described in docs/development.md. They use environment variables provided by Claude Code.

## Navigation
- **Parent Folder**: [Up: Root README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Requires ruff and optionally typos installed. Customize hooks.json to adjust behavior; test thoroughly to ensure they don't interrupt workflows.
