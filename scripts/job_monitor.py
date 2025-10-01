#!/usr/bin/env python3
"""
Job Queue Monitoring Utility

This script provides real-time monitoring of the job queue system,
showing deduplication stats, job counts, and helping identify stacking issues.

Usage:
    python scripts/job_monitor.py [--continuous] [--job-type JOB_TYPE]
"""

import asyncio
import argparse
from datetime import datetime
from typing import Dict, Any

from app.services.infrastructure.startup_service import startup_service


def format_timestamp(ts: str) -> str:
    """Format timestamp for display."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except Exception as e:
        print(f"Error formatting timestamp: {e}")
        return ts


def display_job_stats(stats: Dict[str, Any], job_type_filter: str = None):
    """Display formatted job statistics."""
    print(f"\n{'=' * 80}")
    print(f"🔍 Job Queue Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}")

    # System overview
    health = startup_service.get_health_status()
    print(f"📊 System Status: {health['status'].upper()}")
    print(
        f"⚙️  Workers: {health['jobs']['running']} | Registered Jobs: {health['jobs']['registered']}"
    )
    print(f"✅ Total Executions: {health['jobs']['total_executions']}")

    # Configuration status
    config_info = stats.get("deduplication_config", {})
    print("\n🔧 Deduplication Config:")
    print(f"   • Enabled: {config_info.get('enabled', 'N/A')}")
    print(f"   • Aggressive: {config_info.get('aggressive_enabled', 'N/A')}")
    print(f"   • Stacking Prevention: {config_info.get('stacking_prevention', 'N/A')}")
    print(
        f"   • Monitoring Jobs: {', '.join(config_info.get('monitoring_job_types', []))}"
    )

    # Job queue status
    executor_stats = stats.get("executor_stats", {})
    tracking_stats = stats.get("tracking_stats", {})

    print("\n📋 Queue Status:")
    print(f"   • Total Active Jobs: {executor_stats.get('total_active', 0)}")
    print(f"   • Total Pending Jobs: {executor_stats.get('total_pending', 0)}")
    print(f"   • Active Job Types: {tracking_stats.get('total_active_types', 0)}")
    print(f"   • Dead Letter Queue: {executor_stats.get('dead_letter_count', 0)}")

    # Active jobs by type
    active_jobs = executor_stats.get("active_jobs", {})
    pending_jobs = executor_stats.get("pending_jobs", {})

    if active_jobs or pending_jobs:
        print("\n🔄 Jobs by Type:")
        all_job_types = set(active_jobs.keys()) | set(pending_jobs.keys())

        for job_type in sorted(all_job_types):
            if job_type_filter and job_type_filter not in job_type:
                continue

            active_count = active_jobs.get(job_type, 0)
            pending_count = pending_jobs.get(job_type, 0)

            status_icon = "🔥" if active_count > 0 else "💤"
            warning = (
                " ⚠️  STACKING!"
                if pending_count > 1
                and job_type in config_info.get("monitoring_job_types", [])
                else ""
            )

            print(
                f"   {status_icon} {job_type:25} | Active: {active_count:2d} | Pending: {pending_count:2d}{warning}"
            )

    # Recent metrics for specific job type if requested
    if job_type_filter:
        job_details = startup_service.get_job_metrics().get(job_type_filter)
        if job_details:
            print(f"\n📈 {job_type_filter} Details:")
            metrics = job_details.get("metrics", {})
            print(
                f"   • Success Rate: {metrics.get('successful_executions', 0)}/{metrics.get('total_executions', 0)}"
            )
            print(
                f"   • Avg Execution Time: {metrics.get('avg_execution_time', 0):.2f}s"
            )
            print(f"   • Currently Running: {metrics.get('current_running', 0)}")
            if metrics.get("last_execution"):
                print(
                    f"   • Last Execution: {format_timestamp(metrics['last_execution'])}"
                )


async def monitor_continuously(job_type_filter: str = None, interval: int = 5):
    """Continuously monitor job queue status."""
    print("🚀 Starting continuous job monitoring...")
    print(f"📡 Refresh interval: {interval} seconds")
    print("Press Ctrl+C to stop")

    try:
        while True:
            try:
                stats = startup_service.get_comprehensive_metrics()
                display_job_stats(stats, job_type_filter)

                # Show trend info
                prev_stats = getattr(monitor_continuously, "_prev_stats", None)
                if prev_stats:
                    curr_pending = stats.get("executor_stats", {}).get(
                        "total_pending", 0
                    )
                    prev_pending = prev_stats.get("executor_stats", {}).get(
                        "total_pending", 0
                    )

                    if curr_pending > prev_pending:
                        print(
                            f"📈 Trend: Queue growing (+{curr_pending - prev_pending})"
                        )
                    elif curr_pending < prev_pending:
                        print(
                            f"📉 Trend: Queue shrinking ({curr_pending - prev_pending})"
                        )
                    else:
                        print(f"➡️  Trend: Queue stable ({curr_pending})")

                monitor_continuously._prev_stats = stats

            except Exception as e:
                print(f"❌ Error getting stats: {e}")

            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")


async def show_single_snapshot(job_type_filter: str = None):
    """Show a single snapshot of the job queue status."""
    try:
        stats = startup_service.get_comprehensive_metrics()
        display_job_stats(stats, job_type_filter)

        # Show recent events if available
        if job_type_filter:
            job_details = startup_service.job_manager.get_job_details(job_type_filter)
            if job_details and job_details.get("recent_events"):
                print(f"\n📝 Recent {job_type_filter} Events:")
                for event in job_details["recent_events"][:5]:  # Last 5 events
                    ts = format_timestamp(event["timestamp"])
                    print(
                        f"   {ts} | {event['event_type']} | Duration: {event.get('duration', 'N/A')}s"
                    )

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Monitor AIBTC job queue system")
    parser.add_argument(
        "-c",
        "--continuous",
        action="store_true",
        help="Run continuously with live updates",
    )
    parser.add_argument(
        "-j",
        "--job-type",
        type=str,
        help="Filter to specific job type (e.g., chain_state_monitor)",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=5,
        help="Update interval in seconds (default: 5)",
    )

    args = parser.parse_args()

    if args.continuous:
        asyncio.run(monitor_continuously(args.job_type, args.interval))
    else:
        exit_code = asyncio.run(show_single_snapshot(args.job_type))
        exit(exit_code)


if __name__ == "__main__":
    main()
