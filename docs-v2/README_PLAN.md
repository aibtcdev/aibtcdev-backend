# README Documentation Plan

## Overview
This document outlines the plan for creating consistent README.md files throughout the repository, starting from the deepest folders and working upwards. The goal is to provide technical documentation that describes folder purposes, components, relationships, and navigation, effectively "gluing" the repo together.

## README Template
See [README_TEMPLATE.md](./README_TEMPLATE.md) for the standardized structure used for all folder READMEs.

## Key Principles
- **Order**: Process folders from deepest to shallowest (e.g., depth 5+ first, then depth 4, etc.). Group them by depth for efficiency.
- **Iteration Process**:
  1. Focus on a specific folder (or small group) per iteration.
  2. Generate README content based on the template, incorporating file contexts and relationships.
  3. Incorporate relationships: Reference lower-level READMEs as we ascend.
  4. Review and refine based on feedback.
  5. Complete with a root-level README.md.
- **Depth Calculation**: Relative to the root.
- **Scope**: Skip ignored/empty folders. Use Markdown; include diagrams if needed for complex relationships.
- **Estimated Iterations**: ~15-20 to cover all directories.

## Folder Processing Order (Bottom-Up)

- **Group 1: Depth 6 (Deepest Leaves)**
  - `app/services/integrations/webhooks/chainhook/handlers/` (Deepest handlers for Chainhook events).

- **Group 2: Depth 5**
  - `app/services/ai/simple_workflows/prompts/` (Prompt templates and loaders).
  - `app/services/ai/simple_workflows/processors/` (Processors for images, Twitter, etc.).
  - `app/services/infrastructure/job_management/tasks/` (Specific job tasks like DAO deployment).
  - `app/services/integrations/webhooks/chainhook/` (Chainhook webhook handling).
  - `app/services/integrations/webhooks/dao/` (DAO webhook parsing).

- **Group 3: Depth 4**
  - `app/services/ai/embeddings/` (Embedding services).
  - `app/services/ai/simple_workflows/` (AI workflow orchestrators and models).
  - `app/services/communication/discord/` (Discord services).
  - `app/services/infrastructure/job_management/` (Job executors, decorators, etc.).
  - `app/services/integrations/hiro/` (Hiro API integrations).
  - `app/services/integrations/webhooks/` (Base webhook services).

- **Group 4: Depth 3**
  - `app/services/ai/` (AI services).
  - `app/services/communication/` (Communication services like Twitter/Telegram).
  - `app/services/core/` (Core DAO services).
  - `app/services/infrastructure/` (Job management and startup).
  - `app/services/integrations/` (Integration services).
  - `app/services/processing/` (Data processing like Twitter).
  - `services/runner/tasks/` (Runner tasks).

- **Group 5: Depth 2**
  - `app/api/` (API routers and endpoints).
  - `app/backend/` (Backend abstractions and models).
  - `app/lib/` (Utility libraries).
  - `app/middleware/` (Logging middleware).
  - `app/services/` (All services).
  - `app/tools/` (Tool implementations).
  - `services/runner/` (Runner services).
  - `services/webhooks/` (Webhooks services).
  - `services/workflows/` (Workflows services).

- **Group 6: Depth 1**
  - `app/` (Main application code).
  - `docs/` (Documentation).
  - `docs-v2/` (Version 2 documentation).
  - `examples/` (Example files).
  - `scripts/` (Utility scripts).
  - `services/` (Top-level services).
  - `supabase/` (Supabase configurations).

- **Group 7: Root (Depth 0)**
  - Root folder (synthesize everything into a main README.md).

## Maintenance and Re-running
To keep documentation current as the repository changes (e.g., new files/folders added), follow these steps:
1. Remove all **[Completed]** markers from the "Folder Processing Order" section.
2. Generate an updated repository structure by running `tree -I "__pycache__|agent-tools-ts"` from the root, then review and update the group listings if new folders are added.
3. Re-iterate through the groups bottom-up, regenerating or updating README.md files using the template.
4. Use tools like diff or git to compare changes and apply selectively.
This process ensures documentation remains accurate and comprehensive over time.
