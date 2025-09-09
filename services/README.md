# services Folder Documentation

## Overview
This top-level folder organizes service-related components, including runners, webhooks, and workflows. It provides entry points for service executions.

## Key Components
- **Files**:
  - (None specified.)

- **Subfolders**:
  - runner/: Runner services. [runner README](./runner/README.md) - Task runners.
  - webhooks/: Top-level webhooks. [webhooks README](./webhooks/README.md) - Webhook handling.
  - workflows/: Workflow definitions. [workflows README](./workflows/README.md) - Custom workflows.

## Relationships and Integration
Complements app/services/ for additional service layers; may run parallel to app/worker.py.

## Navigation
- **Parent Folder**: [Up: Root README](../README.md)
- **Child Folders** (if applicable): 
  - [Down: runner README](./runner/README.md)
  - [Down: webhooks README](./webhooks/README.md)
  - [Down: workflows README](./workflows/README.md)

## Additional Notes
Extend for microservices if needed.
