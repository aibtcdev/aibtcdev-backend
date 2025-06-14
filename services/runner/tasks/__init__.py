"""Task runners for scheduled and on-demand jobs.

Tasks are automatically discovered and registered using the @job decorator.
To create a new task:

1. Create a new .py file in this directory
2. Import the @job decorator: from ..decorators import job
3. Decorate your task class with @job("your_job_type", ...)
4. That's it! The task will be automatically discovered and registered.

Example:
    @job(
        "my_new_job",
        name="My New Job",
        description="Does something useful",
        interval_seconds=120,
        priority=JobPriority.NORMAL,
        max_concurrent=1,
    )
    class MyNewJobTask(BaseTask[MyJobResult]):
        async def _execute_impl(self, context: JobContext) -> List[MyJobResult]:
            # Implementation here
            pass
"""

# Auto-discovery handles all task imports and registrations
# No manual imports needed here anymore!

__all__ = []  # Auto-discovery populates the registry
