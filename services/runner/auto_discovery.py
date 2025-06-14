"""Auto-discovery module for job tasks."""

import importlib
from pathlib import Path

from lib.logger import configure_logger

from .decorators import JobRegistry

logger = configure_logger(__name__)


def discover_and_register_tasks() -> None:
    """Discover and register all job tasks from the tasks directory."""
    try:
        tasks_dir = Path(__file__).parent / "tasks"
        if not tasks_dir.exists():
            logger.warning(f"Tasks directory not found: {tasks_dir}")
            return

        # Import all Python modules in the tasks directory
        tasks_package = "services.runner.tasks"
        discovered_modules = []

        # Get all .py files in the tasks directory
        for file_path in tasks_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue  # Skip __init__.py and __pycache__

            module_name = file_path.stem
            full_module_name = f"{tasks_package}.{module_name}"

            try:
                logger.debug(f"Importing task module: {full_module_name}")
                importlib.import_module(full_module_name)
                discovered_modules.append(module_name)
                logger.debug(f"Successfully imported: {full_module_name}")
            except ImportError as e:
                logger.warning(
                    f"Failed to import task module {full_module_name}: {str(e)}"
                )
            except Exception as e:
                logger.error(
                    f"Error importing task module {full_module_name}: {str(e)}",
                    exc_info=True,
                )

        # Log discovered tasks
        registered_tasks = JobRegistry.list_jobs()
        if registered_tasks:
            logger.info(
                f"Auto-discovered and registered {len(registered_tasks)} job tasks from {len(discovered_modules)} modules:"
            )
            for job_type, metadata in registered_tasks.items():
                logger.info(
                    f"  - {job_type}: {metadata.name} (enabled: {metadata.enabled}, interval: {metadata.interval_seconds}s)"
                )
        else:
            logger.warning("No job tasks were discovered and registered")

        # Validate dependencies
        dependency_issues = JobRegistry.validate_dependencies()
        if dependency_issues:
            logger.warning("Dependency validation issues found:")
            for issue in dependency_issues:
                logger.warning(f"  - {issue}")
        else:
            logger.debug("All job dependencies validated successfully")

        # Log dynamic job types that were created
        from .base import JobType

        all_job_types = JobType.get_all_job_types()
        if all_job_types:
            logger.info(
                f"Dynamic job types registered: {', '.join(all_job_types.keys())}"
            )

    except Exception as e:
        logger.error(f"Error during task discovery: {str(e)}", exc_info=True)


def reload_tasks() -> None:
    """Reload all tasks (useful for development)."""
    logger.info("Reloading all job tasks...")

    # Clear existing registry
    JobRegistry.clear_registry()

    # Clear dynamic job types
    from .base import JobType

    JobType._job_types = {}

    # Re-discover tasks
    discover_and_register_tasks()

    logger.info("Task reload completed")


def get_task_summary() -> dict:
    """Get a summary of all discovered tasks."""
    registered_tasks = JobRegistry.list_jobs()
    enabled_tasks = JobRegistry.list_enabled_jobs()

    summary = {
        "total_tasks": len(registered_tasks),
        "enabled_tasks": len(enabled_tasks),
        "disabled_tasks": len(registered_tasks) - len(enabled_tasks),
        "tasks_by_priority": {},
        "tasks_by_type": {},
        "dependency_issues": JobRegistry.validate_dependencies(),
        "dynamic_job_types": list(registered_tasks.keys()),
    }

    # Group by priority
    for job_type, metadata in registered_tasks.items():
        priority = str(metadata.priority)
        if priority not in summary["tasks_by_priority"]:
            summary["tasks_by_priority"][priority] = []
        summary["tasks_by_priority"][priority].append(str(job_type))

    # Group by type (enabled/disabled)
    summary["tasks_by_type"]["enabled"] = [str(jt) for jt in enabled_tasks.keys()]
    summary["tasks_by_type"]["disabled"] = [
        str(jt) for jt, meta in registered_tasks.items() if not meta.enabled
    ]

    return summary


# Auto-discover tasks when this module is imported
discover_and_register_tasks()
