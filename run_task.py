#!/usr/bin/env python3
"""
CLI script for running tasks on demand.

This script provides a command-line interface to interact with the job management system,
allowing you to list available tasks, run specific tasks, and monitor their execution.

Usage:
    python run_task.py list                    # List all available tasks
    python run_task.py run <task_name>         # Run a specific task
    python run_task.py info <task_name>        # Show task information
    python run_task.py status                  # Show system status
    python run_task.py metrics [task_name]     # Show task metrics
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import List

# Add the current directory to the Python path
sys.path.insert(0, ".")

from app.services.infrastructure.job_management import (
    JobRegistry,
    discover_and_register_tasks,
    get_task_summary,
    get_metrics_collector,
    get_performance_monitor,
)
from app.services.infrastructure.job_management.base import JobType
from app.services.infrastructure.job_management.decorators import JobPriority
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class TaskCLI:
    """Command-line interface for task management."""

    def __init__(self):
        self.metrics_collector = get_metrics_collector()
        self.performance_monitor = get_performance_monitor()

    def setup_argparser(self) -> argparse.ArgumentParser:
        """Set up command-line argument parser."""
        parser = argparse.ArgumentParser(
            description="CLI tool for running tasks on demand",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
    python run_task.py list
    python run_task.py run agent_account_deployer
    python run_task.py info dao_deployment
    python run_task.py status
    python run_task.py metrics chain_state_monitor
            """,
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # List command
        list_parser = subparsers.add_parser("list", help="List all available tasks")
        list_parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format (default: table)",
        )
        list_parser.add_argument(
            "--priority",
            choices=["low", "normal", "medium", "high", "critical"],
            help="Filter by priority level",
        )
        list_parser.add_argument(
            "--enabled-only", action="store_true", help="Show only enabled tasks"
        )

        # Run command
        run_parser = subparsers.add_parser("run", help="Run a specific task")
        run_parser.add_argument("task_name", help="Name of the task to run")
        run_parser.add_argument(
            "--parameters",
            type=str,
            help="JSON string of parameters to pass to the task",
        )
        run_parser.add_argument(
            "--timeout", type=int, default=300, help="Timeout in seconds (default: 300)"
        )
        run_parser.add_argument(
            "--verbose", action="store_true", help="Show verbose output"
        )

        # Info command
        info_parser = subparsers.add_parser("info", help="Show task information")
        info_parser.add_argument("task_name", help="Name of the task to show info for")

        # Status command
        status_parser = subparsers.add_parser("status", help="Show system status")
        status_parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format (default: table)",
        )

        # Metrics command
        metrics_parser = subparsers.add_parser("metrics", help="Show task metrics")
        metrics_parser.add_argument(
            "task_name",
            nargs="?",
            help="Name of the task to show metrics for (optional)",
        )
        metrics_parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format (default: table)",
        )

        return parser

    def print_table(self, headers: List[str], rows: List[List[str]], title: str = None):
        """Print data in table format."""
        if title:
            print(f"\n{title}")
            print("=" * len(title))

        if not rows:
            print("No data available")
            return

        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Print header
        header_row = " | ".join(
            header.ljust(col_widths[i]) for i, header in enumerate(headers)
        )
        print(f"\n{header_row}")
        print("-" * len(header_row))

        # Print rows
        for row in rows:
            data_row = " | ".join(
                str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)
            )
            print(data_row)

        print()

    def list_tasks(self, args):
        """List all available tasks."""
        try:
            # Ensure tasks are discovered
            discover_and_register_tasks()

            # Get all registered tasks
            registered_tasks = JobRegistry.list_jobs()

            if not registered_tasks:
                print("No tasks found. Make sure tasks are properly registered.")
                return

            # Filter by priority if specified
            if args.priority:
                priority_filter = JobPriority[args.priority.upper()]
                registered_tasks = {
                    job_type: metadata
                    for job_type, metadata in registered_tasks.items()
                    if metadata.priority == priority_filter
                }

            # Filter by enabled status if specified
            if args.enabled_only:
                registered_tasks = {
                    job_type: metadata
                    for job_type, metadata in registered_tasks.items()
                    if metadata.enabled
                }

            if args.format == "json":
                task_data = {}
                for job_type, metadata in registered_tasks.items():
                    task_data[str(job_type)] = {
                        "name": metadata.name,
                        "description": metadata.description,
                        "enabled": metadata.enabled,
                        "priority": str(metadata.priority),
                        "interval_seconds": metadata.interval_seconds,
                        "max_retries": metadata.max_retries,
                        "timeout_seconds": metadata.timeout_seconds,
                        "max_concurrent": metadata.max_concurrent,
                        "requires_wallet": metadata.requires_wallet,
                        "requires_twitter": metadata.requires_twitter,
                        "requires_discord": metadata.requires_discord,
                        "requires_blockchain": metadata.requires_blockchain,
                        "requires_ai": metadata.requires_ai,
                    }
                print(json.dumps(task_data, indent=2))
            else:
                # Table format
                headers = [
                    "Task Name",
                    "Display Name",
                    "Status",
                    "Priority",
                    "Interval",
                    "Description",
                ]
                rows = []

                for job_type, metadata in registered_tasks.items():
                    status = "✓ Enabled" if metadata.enabled else "✗ Disabled"
                    interval = f"{metadata.interval_seconds}s"
                    description = (
                        metadata.description[:50] + "..."
                        if len(metadata.description) > 50
                        else metadata.description
                    )

                    rows.append(
                        [
                            str(job_type),
                            metadata.name,
                            status,
                            str(metadata.priority),
                            interval,
                            description,
                        ]
                    )

                self.print_table(headers, rows, f"Available Tasks ({len(rows)} total)")

        except Exception as e:
            logger.error(f"Error listing tasks: {str(e)}", exc_info=True)
            print(f"Error listing tasks: {str(e)}")

    async def run_task(self, args):
        """Run a specific task."""
        try:
            # Ensure tasks are discovered
            discover_and_register_tasks()

            # Parse parameters if provided
            parameters = None
            if args.parameters:
                try:
                    parameters = json.loads(args.parameters)
                except json.JSONDecodeError as e:
                    print(f"Error parsing parameters JSON: {e}")
                    return

            # Check if task exists
            task_type = JobType.get_or_create(args.task_name)
            task_metadata = JobRegistry.get_metadata(task_type)

            if not task_metadata:
                print(f"Task '{args.task_name}' not found.")
                print("Use 'python run_task.py list' to see available tasks.")
                return

            print(f"Running task: {task_metadata.name}")
            print(f"Description: {task_metadata.description}")

            if args.verbose:
                print(f"Priority: {task_metadata.priority}")
                print(f"Timeout: {args.timeout}s")
                print(f"Parameters: {parameters}")

            print("\nExecuting task...")
            start_time = datetime.now()

            # Run the task
            try:
                # Get the task instance from the new registry
                task_instance = JobRegistry.get_instance(task_type)
                if not task_instance:
                    print(f"❌ No task instance found for: {args.task_name}")
                    return

                # Create context for the task
                from app.services.infrastructure.job_management.base import (
                    JobContext,
                    RunnerConfig,
                )

                context = JobContext(
                    job_type=task_type,
                    config=RunnerConfig(),
                    parameters=parameters or {},
                )

                # Execute with validation
                async def execute_with_validation():
                    # Validate first
                    if not await task_instance.validate(context):
                        raise ValueError(f"Task validation failed for {args.task_name}")

                    # Execute the task
                    return await task_instance.execute(context)

                results = await asyncio.wait_for(
                    execute_with_validation(), timeout=args.timeout
                )

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                print(f"\nTask completed in {duration:.2f} seconds")
                print(f"Results: {len(results)} item(s)")

                # Display results
                for i, result in enumerate(results, 1):
                    print(f"\nResult {i}:")
                    print(f"  Success: {result.success}")
                    print(f"  Message: {result.message}")

                    if hasattr(result, "error") and result.error:
                        print(f"  Error: {result.error}")

                    if args.verbose:
                        # Show additional result fields
                        for attr in dir(result):
                            if not attr.startswith("_") and attr not in [
                                "success",
                                "message",
                                "error",
                            ]:
                                value = getattr(result, attr)
                                if value is not None:
                                    print(f"  {attr}: {value}")

            except asyncio.TimeoutError:
                print(f"\nTask timed out after {args.timeout} seconds")
            except Exception as e:
                print(f"\nTask failed with error: {str(e)}")
                if args.verbose:
                    logger.error(f"Task execution error: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error running task: {str(e)}", exc_info=True)
            print(f"Error running task: {str(e)}")

    def show_task_info(self, args):
        """Show detailed information about a specific task."""
        try:
            # Ensure tasks are discovered
            discover_and_register_tasks()

            # Get task metadata
            task_type = JobType.get_or_create(args.task_name)
            task_metadata = JobRegistry.get_metadata(task_type)

            if not task_metadata:
                print(f"Task '{args.task_name}' not found.")
                return

            print(f"\nTask Information: {task_metadata.name}")
            print("=" * (len(task_metadata.name) + 18))

            print(f"Task Name: {args.task_name}")
            print(f"Display Name: {task_metadata.name}")
            print(f"Description: {task_metadata.description}")
            print(f"Version: {task_metadata.version}")
            print(f"Status: {'✓ Enabled' if task_metadata.enabled else '✗ Disabled'}")
            print(f"Priority: {task_metadata.priority}")
            print(f"Interval: {task_metadata.interval_seconds} seconds")
            print(f"Max Retries: {task_metadata.max_retries}")
            print(f"Retry Delay: {task_metadata.retry_delay_seconds} seconds")
            print(f"Timeout: {task_metadata.timeout_seconds} seconds")
            print(f"Max Concurrent: {task_metadata.max_concurrent}")
            print(f"Batch Size: {task_metadata.batch_size}")
            print(
                f"Dead Letter Queue: {'✓ Enabled' if task_metadata.enable_dead_letter_queue else '✗ Disabled'}"
            )
            print(
                f"Preserve Order: {'✓ Yes' if task_metadata.preserve_order else '✗ No'}"
            )
            print(f"Idempotent: {'✓ Yes' if task_metadata.idempotent else '✗ No'}")

            # Requirements
            requirements = []
            if task_metadata.requires_wallet:
                requirements.append("Wallet")
            if task_metadata.requires_twitter:
                requirements.append("Twitter")
            if task_metadata.requires_discord:
                requirements.append("Discord")
            if task_metadata.requires_blockchain:
                requirements.append("Blockchain")
            if task_metadata.requires_ai:
                requirements.append("AI")

            print(
                f"Requirements: {', '.join(requirements) if requirements else 'None'}"
            )

            # Dependencies
            if task_metadata.dependencies:
                print(f"Dependencies: {', '.join(task_metadata.dependencies)}")
            else:
                print("Dependencies: None")

            # Configuration overrides
            if task_metadata.config_overrides:
                print(f"Config Overrides: {task_metadata.config_overrides}")

        except Exception as e:
            logger.error(f"Error showing task info: {str(e)}", exc_info=True)
            print(f"Error showing task info: {str(e)}")

    def show_status(self, args):
        """Show system status."""
        try:
            # Ensure tasks are discovered
            discover_and_register_tasks()

            # Get task summary
            task_summary = get_task_summary()

            # Get system metrics
            system_metrics = self.metrics_collector.get_system_metrics()
            health_status = self.metrics_collector.get_health_status()
            performance_summary = self.performance_monitor.get_performance_summary()

            if args.format == "json":
                status_data = {
                    "task_summary": task_summary,
                    "system_metrics": system_metrics,
                    "health_status": health_status,
                    "performance_summary": performance_summary,
                }
                print(json.dumps(status_data, indent=2, default=str))
            else:
                # Table format
                print("\nSystem Status")
                print("=" * 13)

                print(f"Health Status: {health_status['status'].upper()}")
                print(f"Uptime: {system_metrics['uptime_seconds']:.1f} seconds")
                print(f"Total Tasks: {task_summary['total_tasks']}")
                print(f"Enabled Tasks: {task_summary['enabled_tasks']}")
                print(f"Disabled Tasks: {task_summary['disabled_tasks']}")
                print(f"Total Executions: {system_metrics['total_executions']}")
                print(f"Success Rate: {system_metrics['success_rate']:.1%}")
                print(f"Active Job Types: {system_metrics['active_job_types']}")

                if health_status["issues"]:
                    print("\nHealth Issues:")
                    for issue in health_status["issues"]:
                        print(f"  - {issue}")

                if task_summary["dependency_issues"]:
                    print("\nDependency Issues:")
                    for issue in task_summary["dependency_issues"]:
                        print(f"  - {issue}")

                # Performance alerts
                alerts = performance_summary.get("alerts", [])
                if alerts:
                    print("\nPerformance Alerts:")
                    for alert in alerts:
                        print(f"  - {alert}")

        except Exception as e:
            logger.error(f"Error showing status: {str(e)}", exc_info=True)
            print(f"Error showing status: {str(e)}")

    def show_metrics(self, args):
        """Show task metrics."""
        try:
            # Ensure tasks are discovered
            discover_and_register_tasks()

            if args.task_name:
                # Show metrics for specific task
                task_type = JobType.get_or_create(args.task_name)
                metrics = self.metrics_collector.get_metrics(task_type)

                if not metrics:
                    print(f"No metrics found for task '{args.task_name}'")
                    return

                task_metrics = list(metrics.values())[0]

                if args.format == "json":
                    metrics_data = {
                        "job_type": str(task_metrics.job_type),
                        "total_executions": task_metrics.total_executions,
                        "successful_executions": task_metrics.successful_executions,
                        "failed_executions": task_metrics.failed_executions,
                        "retried_executions": task_metrics.retried_executions,
                        "dead_letter_executions": task_metrics.dead_letter_executions,
                        "avg_execution_time": task_metrics.avg_execution_time,
                        "min_execution_time": task_metrics.min_execution_time,
                        "max_execution_time": task_metrics.max_execution_time,
                        "current_running": task_metrics.current_running,
                        "max_concurrent_reached": task_metrics.max_concurrent_reached,
                        "last_execution": task_metrics.last_execution.isoformat()
                        if task_metrics.last_execution
                        else None,
                        "last_success": task_metrics.last_success.isoformat()
                        if task_metrics.last_success
                        else None,
                        "last_failure": task_metrics.last_failure.isoformat()
                        if task_metrics.last_failure
                        else None,
                    }
                    print(json.dumps(metrics_data, indent=2))
                else:
                    print(f"\nMetrics for Task: {args.task_name}")
                    print("=" * (len(args.task_name) + 18))

                    print(f"Total Executions: {task_metrics.total_executions}")
                    print(f"Successful: {task_metrics.successful_executions}")
                    print(f"Failed: {task_metrics.failed_executions}")
                    print(f"Retried: {task_metrics.retried_executions}")
                    print(f"Dead Letter: {task_metrics.dead_letter_executions}")
                    print(f"Currently Running: {task_metrics.current_running}")
                    print(
                        f"Max Concurrent Reached: {task_metrics.max_concurrent_reached}"
                    )

                    if task_metrics.total_executions > 0:
                        success_rate = (
                            task_metrics.successful_executions
                            / task_metrics.total_executions
                        )
                        print(f"Success Rate: {success_rate:.1%}")

                    print(f"Avg Execution Time: {task_metrics.avg_execution_time:.2f}s")
                    if task_metrics.min_execution_time is not None:
                        print(
                            f"Min Execution Time: {task_metrics.min_execution_time:.2f}s"
                        )
                    if task_metrics.max_execution_time is not None:
                        print(
                            f"Max Execution Time: {task_metrics.max_execution_time:.2f}s"
                        )

                    if task_metrics.last_execution:
                        print(f"Last Execution: {task_metrics.last_execution}")
                    if task_metrics.last_success:
                        print(f"Last Success: {task_metrics.last_success}")
                    if task_metrics.last_failure:
                        print(f"Last Failure: {task_metrics.last_failure}")
            else:
                # Show metrics for all tasks
                all_metrics = self.metrics_collector.get_metrics()

                if args.format == "json":
                    metrics_data = {}
                    for job_type, metrics in all_metrics.items():
                        metrics_data[str(job_type)] = {
                            "total_executions": metrics.total_executions,
                            "successful_executions": metrics.successful_executions,
                            "failed_executions": metrics.failed_executions,
                            "success_rate": metrics.successful_executions
                            / metrics.total_executions
                            if metrics.total_executions > 0
                            else 0,
                            "avg_execution_time": metrics.avg_execution_time,
                            "current_running": metrics.current_running,
                            "last_execution": metrics.last_execution.isoformat()
                            if metrics.last_execution
                            else None,
                        }
                    print(json.dumps(metrics_data, indent=2))
                else:
                    headers = [
                        "Task",
                        "Total",
                        "Success",
                        "Failed",
                        "Success Rate",
                        "Avg Time",
                        "Running",
                        "Last Execution",
                    ]
                    rows = []

                    for job_type, metrics in all_metrics.items():
                        success_rate = (
                            metrics.successful_executions / metrics.total_executions
                            if metrics.total_executions > 0
                            else 0
                        )
                        last_exec = (
                            metrics.last_execution.strftime("%Y-%m-%d %H:%M:%S")
                            if metrics.last_execution
                            else "Never"
                        )

                        rows.append(
                            [
                                str(job_type),
                                str(metrics.total_executions),
                                str(metrics.successful_executions),
                                str(metrics.failed_executions),
                                f"{success_rate:.1%}",
                                f"{metrics.avg_execution_time:.2f}s",
                                str(metrics.current_running),
                                last_exec,
                            ]
                        )

                    self.print_table(headers, rows, "Task Metrics")

        except Exception as e:
            logger.error(f"Error showing metrics: {str(e)}", exc_info=True)
            print(f"Error showing metrics: {str(e)}")

    async def main(self):
        """Main CLI entry point."""
        parser = self.setup_argparser()
        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            return

        try:
            if args.command == "list":
                self.list_tasks(args)
            elif args.command == "run":
                await self.run_task(args)
            elif args.command == "info":
                self.show_task_info(args)
            elif args.command == "status":
                self.show_status(args)
            elif args.command == "metrics":
                self.show_metrics(args)
            else:
                parser.print_help()
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
        except Exception as e:
            logger.error(f"CLI error: {str(e)}", exc_info=True)
            print(f"Error: {str(e)}")


if __name__ == "__main__":
    cli = TaskCLI()
    asyncio.run(cli.main())
