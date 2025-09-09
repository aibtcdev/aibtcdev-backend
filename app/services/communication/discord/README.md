# discord Folder Documentation

## Overview
This folder provides Discord integration services, including factory and service classes for sending messages via webhooks. It uses configuration-based initialization and supports embeds and TTS.

## Key Components
- **Files**:
  - discord_factory.py: Factory for creating Discord services.
  - discord_service.py: Implements DiscordService for message sending.
  - __init__.py: Initialization file for the package.

- **Subfolders**:
  - (None)

## Relationships and Integration
Services here are used in job tasks like discord_task.py in app/services/infrastructure/job_management/tasks/ and integrate with config from app/config.py. May be called from communication orchestration in the parent folder.

## Navigation
- **Parent Folder**: [Up: communication Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Configure webhook URLs securely; test message sending with rate limits in mind.
