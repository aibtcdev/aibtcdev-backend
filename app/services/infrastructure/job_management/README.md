# job_management Folder Documentation

## Overview
This folder manages job scheduling, execution, and monitoring, including auto-discovery of tasks, decorators for job registration, and metrics collection. It uses dataclass configs, async executors, and dynamic registration for scalable background processing.

## Key Components
- **Files**:
  - [auto_discovery.py](auto_discovery.py): Discovers and registers jobs dynamically.
  - [base.py](base.py): Defines BaseTask, JobType, and RunnerConfig.
  - [decorators.py](decorators.py): Provides @job decorator for task definition.
  - [executor.py](executor.py): Handles job execution.
  - [__init__.py](__init__.py): Initialization file for the package.
  - [job_manager.py](job_manager.py): Manages job scheduling with JobScheduleConfig.
  - [monitoring.py](monitoring.py): Implements MetricsCollector for job metrics.
  - [registry.py](registry.py): Registers discovered jobs.

- **Subfolders**:
  - [tasks/](tasks/): Specific job task implementations. [tasks README](./tasks/README.md) - Individual task definitions.

## Relationships and Integration
Jobs are discovered from the tasks subfolder and executed via the executor, integrating with backend queue messages (app/backend/models.py). Used by startup services in the parent folder and may trigger communications or integrations.

## Navigation
- **Parent Folder**: [Up: infrastructure Folder README](../README.md)
- **Child Folders** (if applicable): 
  - [Down: tasks README](./tasks/README.md)

## Additional Notes
Supports dynamic job types; add monitoring for high-priority jobs.
