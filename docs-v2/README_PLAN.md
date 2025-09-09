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

- **Group 1: Depth 6+ (Deepest Leaves)**
  - `app/services/integrations/webhooks/chainhook/handlers/` (Deepest handlers for Chainhook events). **[Completed]**
  - `app/services/ai/simple_workflows/prompts/` (Prompt templates and loaders). **[Completed]**
  - `app/services/ai/simple_workflows/processors/` (Processors for images, Twitter, etc.). **[Completed]**

- **Group 2: Depth 5**
  - `app/services/integrations/webhooks/chainhook/` (Chainhook webhook handling). **[Completed]**
  - `app/services/integrations/webhooks/dao/` (DAO webhook parsing). **[Completed]**
  - `app/services/ai/simple_workflows/` (AI workflow orchestrators and models). **[Completed]**
  - `app/services/infrastructure/job_management/tasks/` (Specific job tasks like DAO deployment). **[Completed]**
  - `app/services/communication/discord/` (Discord services). **[Completed]**

- **Group 3: Depth 4**
  - `app/services/integrations/webhooks/` (Base webhook services).
  - `app/services/integrations/hiro/` (Hiro API integrations).
  - `app/services/infrastructure/job_management/` (Job executors, decorators, etc.).
  - `app/services/ai/embeddings/` (Embedding services).
  - `app/api/tools/` (API models and routers for tools).

- **Group 4: Depth 3**
  - `app/services/integrations/` (Integration services).
  - `app/services/infrastructure/` (Job management and startup).
  - `app/services/communication/` (Communication services like Twitter/Telegram).
  - `app/services/processing/` (Data processing like Twitter).
  - `app/services/ai/` (AI services).
  - `app/services/core/` (Core DAO services).
  - `supabase/migrations/` (Database migrations).

- **Group 5: Depth 2**
  - `app/services/` (All services).
  - `app/backend/` (Backend abstractions and models).
  - `app/middleware/` (Logging middleware).
  - `app/lib/` (Utility libraries).
  - `app/tools/` (Tool implementations).
  - `app/api/` (API routers and endpoints).
  - `services/runner/tasks/` (Runner tasks – appears minimal from tree).
  - `services/webhooks/` and `services/workflows/` (If they have content).

- **Group 6: Depth 1**
  - `api/`, `app/`, `backend/`, `crews/`, `db/`, `docs/`, `examples/`, `lib/`, `scripts/`, `services/`, `supabase/`, `tools/`, `webhooks/` (Top-level folders).

- **Group 7: Root (Depth 0)**
  - Root folder (synthesize everything into a main README.md).
