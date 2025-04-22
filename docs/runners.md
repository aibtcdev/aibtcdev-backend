# Runners System Documentation

## Overview

The runners system is a core component of the AIBTC backend that manages and executes various automated tasks. It provides a flexible and extensible framework for scheduling and running different types of jobs, from DAO operations to Twitter interactions.

## Architecture

### Core Components

1. **BaseTask**
   - Abstract base class for all runner tasks
   - Provides common functionality for task execution and validation
   - Implements logging and metrics collection
   - Supports generic result types through type parameters

2. **JobManager**
   - Manages scheduled jobs using AsyncIOScheduler
   - Handles job configuration and scheduling
   - Supports enabling/disabling jobs through configuration

3. **JobRegistry**
   - Maintains a registry of available runners
   - Maps job types to their corresponding runner implementations
   - Provides registration and lookup functionality

### Job Types

The system supports several types of jobs:

- `DAO`: General DAO operations
- `DAO_PROPOSAL_VOTE`: Handling DAO proposal voting
- `DAO_PROPOSAL_CONCLUDE`: Concluding DAO proposals
- `DAO_TWEET`: Managing DAO-related tweets
- `TWEET`: General tweet operations
- `AGENT_ACCOUNT_DEPLOY`: Deploying agent accounts

## Configuration

Runners are configured through environment variables and configuration files. Key configuration includes:

- Twitter profile and agent IDs
- Wallet configurations
- Job intervals and scheduling parameters
- Feature toggles for enabling/disabling specific runners

## Job Execution Flow

1. **Initialization**
   - JobManager loads configurations for all available jobs
   - Enabled jobs are scheduled with specified intervals

2. **Execution**
   - Jobs are executed according to their schedule
   - Each execution follows a standard pipeline:
     1. Configuration validation
     2. Prerequisites validation
     3. Task-specific validation
     4. Task execution
     5. Result logging and metrics collection

3. **Error Handling**
   - Comprehensive error handling and logging
   - Support for retries with configurable retry counts
   - Detailed error reporting and metrics

## Runner Implementation

To implement a new runner:

1. Create a new class inheriting from `BaseTask`
2. Define the result type using the generic parameter
3. Implement required methods:
   - `_validate_config`
   - `_validate_prerequisites`
   - `_validate_task_specific`
   - `_execute_impl`
4. Register the runner with `JobRegistry`

Example:
```python
class MyCustomRunner(BaseTask[MyCustomResult]):
    async def _execute_impl(self, context: JobContext) -> List[MyCustomResult]:
        # Implementation here
        pass
```

## Monitoring and Logging

The runner system includes comprehensive logging:

- Task start and completion times
- Success and failure metrics
- Execution duration
- Detailed error information
- Debug-level configuration logging

## Best Practices

1. **Validation**
   - Implement thorough validation in all runners
   - Check prerequisites before execution
   - Validate configuration and parameters

2. **Error Handling**
   - Use specific exception types
   - Provide detailed error messages
   - Implement appropriate retry logic

3. **Logging**
   - Use appropriate log levels
   - Include context in log messages
   - Log metrics for monitoring

4. **Configuration**
   - Use environment variables for sensitive data
   - Implement feature toggles for runners
   - Document configuration requirements

## Security Considerations

- Sensitive configuration is managed through environment variables
- Wallet operations require proper authentication
- Task validation ensures proper authorization
- Error messages are sanitized for security 