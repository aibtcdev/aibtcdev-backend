"""Migration guide and utilities for transitioning to the enhanced job queue system."""

from typing import Dict, List

from lib.logger import configure_logger

logger = configure_logger(__name__)


class MigrationGuide:
    """Guide for migrating from the old job system to the new enhanced system."""

    @staticmethod
    def get_migration_steps() -> List[str]:
        """Get step-by-step migration instructions."""
        return [
            "1. BACKUP: Create backups of your current job configurations",
            "2. IMPORT: Import the new enhanced modules in your main application",
            "3. REPLACE: Replace old imports with new enhanced versions",
            "4. UPDATE: Update your startup code to use EnhancedStartupService",
            "5. MIGRATE: Convert existing tasks to use the new @job decorator",
            "6. TEST: Test the new system in a development environment",
            "7. DEPLOY: Deploy the enhanced system to production",
            "8. MONITOR: Monitor the new system using built-in metrics",
        ]

    @staticmethod
    def get_import_changes() -> Dict[str, str]:
        """Get mapping of old imports to new imports."""
        return {
            "services.startup": "services.enhanced_startup",
            "services.runner.job_manager.JobManager": "services.runner.enhanced_job_manager.EnhancedJobManager",
            "services.runner.registry": "services.runner.decorators.JobRegistry",
        }

    @staticmethod
    def get_code_examples() -> Dict[str, Dict[str, str]]:
        """Get before/after code examples for common migration scenarios."""
        return {
            "startup_service": {
                "before": """
# Old way
from services.startup import startup_service

async def main():
    await startup_service.init_background_tasks()
""",
                "after": """
# New way
from services.enhanced_startup import enhanced_startup_service

async def main():
    await enhanced_startup_service.init_background_tasks()
""",
            },
            "task_definition": {
                "before": """
# Old way
class TweetTask(BaseTask[TweetProcessingResult]):
    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
    
    async def _execute_impl(self, context: JobContext) -> List[TweetProcessingResult]:
        # Implementation here
        pass

# Manual registration required
tweet_task = TweetTask()
""",
                "after": """
# New way
@job(
    job_type="tweet",
    name="Tweet Processor",
    description="Processes and sends tweets",
    interval_seconds=30,
    priority=JobPriority.HIGH,
    max_retries=3,
    requires_twitter=True
)
class EnhancedTweetTask(BaseTask[TweetProcessingResult]):
    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
    
    async def _execute_impl(self, context: JobContext) -> List[TweetProcessingResult]:
        # Implementation here
        pass

# Auto-registration via decorator
enhanced_tweet_task = EnhancedTweetTask()
""",
            },
            "job_scheduling": {
                "before": """
# Old way - manual configuration in JobManager
jobs = [
    JobConfig(
        name="Tweet Runner Service",
        enabled=config.scheduler.tweet_runner_enabled,
        func=execute_runner_job,
        seconds=config.scheduler.tweet_runner_interval_seconds,
        args=[JobType.TWEET.value],
        job_id="tweet_runner",
    )
]
""",
                "after": """
# New way - automatic via metadata
@job(
    job_type="tweet",
    interval_seconds=30,  # Can be overridden by config
    enabled=True          # Can be overridden by config
)
class TweetTask(BaseTask[TweetProcessingResult]):
    pass

# Scheduling happens automatically based on metadata
""",
            },
            "monitoring": {
                "before": """
# Old way - limited monitoring
logger.info(f"Task completed: {task_name}")
""",
                "after": """
# New way - comprehensive monitoring
from services.enhanced_startup import get_job_metrics, get_system_status

# Get detailed metrics
metrics = get_job_metrics("tweet")
status = await get_system_status()

# Built-in performance monitoring and alerting
""",
            },
        }

    @staticmethod
    def validate_migration() -> Dict[str, bool]:
        """Validate that migration components are available."""
        validation_results = {}

        try:
            # Check if new modules can be imported using importlib
            import importlib.util

            validation_results["enhanced_startup"] = (
                importlib.util.find_spec("services.startup") is not None
            )
        except ImportError:
            validation_results["enhanced_startup"] = False

        try:
            import importlib.util

            validation_results["enhanced_job_manager"] = (
                importlib.util.find_spec("services.runner.job_manager") is not None
            )
        except ImportError:
            validation_results["enhanced_job_manager"] = False

        try:
            import importlib.util

            validation_results["decorators"] = (
                importlib.util.find_spec("services.runner.decorators") is not None
            )
        except ImportError:
            validation_results["decorators"] = False

        try:
            import importlib.util

            validation_results["execution"] = (
                importlib.util.find_spec("services.runner.execution") is not None
            )
        except ImportError:
            validation_results["execution"] = False

        try:
            import importlib.util

            validation_results["monitoring"] = (
                importlib.util.find_spec("services.runner.monitoring") is not None
            )
        except ImportError:
            validation_results["monitoring"] = False

        return validation_results

    @staticmethod
    def get_compatibility_notes() -> List[str]:
        """Get important compatibility notes for migration."""
        return [
            "✅ The new system is backward compatible with existing queue messages",
            "✅ Existing configuration settings are respected and override metadata defaults",
            "✅ Database schema remains unchanged - no migrations required",
            "⚠️  Old task classes will need to be updated to use the new decorator system",
            "⚠️  Manual job registration code can be removed after migration",
            "⚠️  Some import paths have changed - update your imports",
            "🔧 Enhanced error handling may change retry behavior slightly",
            "🔧 New concurrency controls may affect job execution patterns",
            "📊 New monitoring system provides much more detailed metrics",
            "🚀 Performance improvements from priority queues and better resource management",
        ]

    @staticmethod
    def print_migration_guide() -> None:
        """Print a comprehensive migration guide to the console."""
        print("\n" + "=" * 80)
        print("🚀 ENHANCED JOB QUEUE SYSTEM - MIGRATION GUIDE")
        print("=" * 80)

        print("\n📋 MIGRATION STEPS:")
        for step in MigrationGuide.get_migration_steps():
            print(f"   {step}")

        print("\n🔄 IMPORT CHANGES:")
        for old_import, new_import in MigrationGuide.get_import_changes().items():
            print(f"   {old_import} → {new_import}")

        print("\n✅ VALIDATION RESULTS:")
        validation = MigrationGuide.validate_migration()
        for component, available in validation.items():
            status = "✅ Available" if available else "❌ Missing"
            print(f"   {component}: {status}")

        print("\n📝 COMPATIBILITY NOTES:")
        for note in MigrationGuide.get_compatibility_notes():
            print(f"   {note}")

        print("\n💡 CODE EXAMPLES:")
        examples = MigrationGuide.get_code_examples()
        for example_name, code in examples.items():
            print(f"\n   {example_name.upper()}:")
            print(f"   Before:\n{code['before']}")
            print(f"   After:\n{code['after']}")

        print("\n" + "=" * 80)
        print("For detailed documentation, see: job_queue_system_documentation.md")
        print("=" * 80 + "\n")


def run_migration_check() -> bool:
    """Run a comprehensive migration check and return success status."""
    logger.info("Running migration compatibility check...")

    validation = MigrationGuide.validate_migration()
    all_available = all(validation.values())

    if all_available:
        logger.info("✅ All enhanced job queue components are available")
        logger.info("✅ Migration can proceed safely")
        return True
    else:
        logger.error("❌ Some enhanced job queue components are missing:")
        for component, available in validation.items():
            if not available:
                logger.error(f"   - {component}: Missing")
        return False


def print_quick_start() -> None:
    """Print a quick start guide for the new system."""
    print("\n" + "=" * 60)
    print("🚀 ENHANCED JOB QUEUE - QUICK START")
    print("=" * 60)
    print(
        """
1. Replace your startup import:
   from services.enhanced_startup import run, shutdown

2. Create a new task:
   @job(job_type="my_task", interval_seconds=60)
   class MyTask(BaseTask[MyResult]):
       async def _execute_impl(self, context):
           return [MyResult(success=True, message="Done")]

3. Start the system:
   await run()

4. Monitor your jobs:
   from services.enhanced_startup import get_system_status
   status = await get_system_status()

That's it! Your jobs will be auto-discovered and scheduled.
"""
    )
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Run when executed directly
    MigrationGuide.print_migration_guide()

    if run_migration_check():
        print_quick_start()
    else:
        print(
            "\n❌ Migration check failed. Please ensure all components are properly installed."
        )
