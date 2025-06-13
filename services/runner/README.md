# Job Runner System - Auto-Discovery

The job runner system uses **auto-discovery** to make adding new jobs incredibly simple. All job types are dynamically registered - there are no hardcoded job types!

## How It Works

The system automatically:
1. 🔍 **Discovers** all task files in `services/runner/tasks/`
2. 📝 **Registers** jobs decorated with `@job`
3. 🏗️ **Creates** JobType enums dynamically
4. ⚙️ **Configures** scheduling and execution

**No hardcoded job types!** Everything is discovered at runtime through the `@job` decorator.

## Adding a New Job (Super Easy!)

### Step 1: Create Your Task File
Create a new `.py` file in `services/runner/tasks/`. That's it for file creation!

### Step 2: Use the @job Decorator
```python
from dataclasses import dataclass
from typing import List

from ..base import BaseTask, JobContext, RunnerResult
from ..decorators import JobPriority, job

@dataclass
class MyJobResult(RunnerResult):
    """Result of my job processing."""
    items_processed: int = 0

@job(
    "my_awesome_job",  # ✨ Job type - automatically creates JobType.MY_AWESOME_JOB
    name="My Awesome Job",
    description="Does awesome things",
    interval_seconds=120,
    priority=JobPriority.NORMAL,
    max_concurrent=2,
    requires_twitter=True,  # Optional: specify requirements
    enabled=True,  # Optional: enable/disable
)
class MyAwesomeJobTask(BaseTask[MyJobResult]):
    """My awesome job task."""
    
    async def _execute_impl(self, context: JobContext) -> List[MyJobResult]:
        # Your job logic here
        return [MyJobResult(success=True, message="Done!", items_processed=10)]
```

### Step 3: That's It!
Your job is automatically:
- ✅ Discovered and registered
- ✅ JobType enum created dynamically
- ✅ Available in the job manager
- ✅ Schedulable and executable
- ✅ Configurable via environment/config

## Dynamic Job Types

🚀 **All job types are dynamic!** No more hardcoded enums or manual registration.

- Job types are created automatically when you use `@job("job_type_name")`
- The system supports any job type name you want
- JobType enums are generated at runtime
- No conflicts or duplicates - each job type is unique

## Configuration

Jobs can be configured via environment variables or config files:

```bash
# Enable/disable a job
MY_AWESOME_JOB_ENABLED=true

# Override interval
MY_AWESOME_JOB_INTERVAL_SECONDS=300

# Alternative naming pattern (backwards compatibility)
MY_AWESOME_JOB_RUNNER_ENABLED=true
MY_AWESOME_JOB_RUNNER_INTERVAL_SECONDS=300
```

## Job Decorator Options

The `@job` decorator supports many options:

```python
@job(
    "job_type",                    # Required: unique job identifier
    name="Human Readable Name",    # Optional: display name
    description="What it does",    # Optional: description
    
    # Scheduling
    interval_seconds=60,           # How often to run
    enabled=True,                  # Enable/disable
    
    # Execution
    priority=JobPriority.NORMAL,   # LOW, NORMAL, HIGH, CRITICAL
    max_retries=3,                 # Retry attempts
    retry_delay_seconds=30,        # Delay between retries
    timeout_seconds=300,           # Execution timeout
    
    # Concurrency
    max_concurrent=1,              # Max parallel executions
    batch_size=10,                 # Items per batch
    
    # Requirements
    requires_wallet=True,          # Needs wallet access
    requires_twitter=True,         # Needs Twitter API
    requires_discord=True,         # Needs Discord API
    
    # Advanced
    dependencies=["other_job"],    # Job dependencies
    preserve_order=False,          # Order sensitive?
    idempotent=True,              # Safe to retry?
)
```

## Migration from Old System

### Before (Manual Registration Required)
1. Add job type to hardcoded `JobType` enum in `base.py`
2. Add config mapping in `job_manager.py`
3. Import and register in `__init__.py`
4. Export in `tasks/__init__.py`
5. Create the task class

### After (Auto-Discovery)
1. Create task file with `@job` decorator
2. Done! 🎉

## Benefits

- 🚀 **Faster development**: No manual registration steps
- 🛡️ **Less error-prone**: No forgetting to register
- 🔧 **Self-documenting**: All config in one place
- 🌟 **Consistent**: Same pattern for all jobs
- 🎯 **Dynamic**: Job types created automatically
- 🔄 **No hardcoded types**: Everything discovered at runtime

## Examples

Check out existing task files for patterns:
- `dao_task.py` - Complex workflow-based task
- `tweet_task.py` - Media handling and chunking
- `discord_task.py` - Webhook integration
- `proposal_embedder.py` - AI service integration

## Troubleshooting

### Job Not Appearing?
1. Check file is in `services/runner/tasks/`
2. Check `@job` decorator is present
3. Check no syntax errors in task file
4. Check logs for import errors

### Configuration Not Working?
1. Use naming pattern: `{job_type}_enabled` or `{job_type}_interval_seconds`
2. Check environment variables
3. Check config file settings

### Need Help?
- Look at existing task examples
- Check the auto-discovery logs
- Use `JobRegistry.list_jobs()` to see registered jobs
- Check dynamic job types with `JobType.__class__.get_all_job_types()` 