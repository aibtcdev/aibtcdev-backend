#!/usr/bin/env python3
"""
Job Deduplication Test Script

This script tests the job deduplication functionality to ensure
it's working correctly and preventing job stacking.

Usage:
    python scripts/test_job_deduplication.py [--job-type JOB_TYPE]
"""

import asyncio
import argparse
import time

from app.services.infrastructure.startup_service import startup_service


async def test_job_deduplication(
    job_type: str = "chain_state_monitor", num_triggers: int = 5
):
    """Test job deduplication by triggering multiple jobs rapidly."""
    print(f"🧪 Testing Job Deduplication for: {job_type}")
    print(f"📊 Triggering {num_triggers} jobs in rapid succession...")
    print("=" * 70)

    # Get initial stats
    initial_stats = startup_service.get_comprehensive_metrics()
    initial_pending = (
        initial_stats.get("executor_stats", {}).get("pending_jobs", {}).get(job_type, 0)
    )
    initial_active = (
        initial_stats.get("executor_stats", {}).get("active_jobs", {}).get(job_type, 0)
    )

    print("📋 Initial State:")
    print(f"   • Active {job_type}: {initial_active}")
    print(f"   • Pending {job_type}: {initial_pending}")
    print()

    # Rapid fire job triggers
    trigger_results = []
    start_time = time.time()

    for i in range(num_triggers):
        print(f"🚀 Triggering job {i + 1}/{num_triggers}...")
        try:
            result = startup_service.trigger_job(job_type)
            trigger_results.append(result)
            print(f"   Result: {result.get('message', 'Unknown')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            trigger_results.append({"success": False, "error": str(e)})

        # Small delay to show rapid triggering
        await asyncio.sleep(0.1)

    trigger_time = time.time() - start_time
    print(f"\n⏱️  Total trigger time: {trigger_time:.2f} seconds")

    # Wait a moment for jobs to be processed/deduplicated
    print("⏳ Waiting 2 seconds for deduplication to process...")
    await asyncio.sleep(2)

    # Get final stats
    final_stats = startup_service.get_comprehensive_metrics()
    final_pending = (
        final_stats.get("executor_stats", {}).get("pending_jobs", {}).get(job_type, 0)
    )
    final_active = (
        final_stats.get("executor_stats", {}).get("active_jobs", {}).get(job_type, 0)
    )

    print("\n📊 Final State:")
    print(f"   • Active {job_type}: {final_active}")
    print(f"   • Pending {job_type}: {final_pending}")

    # Analysis
    print("\n🔍 Analysis:")
    successful_triggers = sum(1 for r in trigger_results if r.get("success", False))
    print(f"   • Jobs triggered: {num_triggers}")
    print(f"   • Successful triggers: {successful_triggers}")
    print("   • Expected final jobs: 1 (due to deduplication)")
    print(f"   • Actual final jobs: {final_active + final_pending}")

    # Deduplication effectiveness
    total_final_jobs = final_active + final_pending
    if total_final_jobs <= 1:
        print("   ✅ PASS: Deduplication working correctly!")
        print(
            f"   💡 {num_triggers - total_final_jobs} jobs were successfully deduplicated"
        )
    else:
        print(f"   ⚠️  WARNING: {total_final_jobs} jobs remaining (expected ≤ 1)")
        print("   💡 Deduplication may not be working optimally")

    # Configuration check
    config_info = final_stats.get("deduplication_config", {})
    print("\n⚙️  Configuration Status:")
    print(f"   • Deduplication enabled: {config_info.get('enabled', 'N/A')}")
    print(f"   • Aggressive mode: {config_info.get('aggressive_enabled', 'N/A')}")
    print(f"   • Stacking prevention: {config_info.get('stacking_prevention', 'N/A')}")

    monitoring_jobs = config_info.get("monitoring_job_types", [])
    is_monitoring_job = job_type in monitoring_jobs
    print(f"   • {job_type} is monitoring job: {is_monitoring_job}")

    if not config_info.get("enabled", False):
        print("   ⚠️  Note: Job deduplication is disabled in configuration")

    return total_final_jobs <= 1


async def test_multiple_job_types():
    """Test deduplication across multiple job types."""
    print("🧪 Testing Multiple Job Type Deduplication")
    print("=" * 50)

    job_types = [
        "chain_state_monitor",
        "chainhook_monitor",
        "agent_wallet_balance_monitor",
    ]
    results = {}

    for job_type in job_types:
        print(f"\n🎯 Testing {job_type}...")
        result = await test_job_deduplication(job_type, 3)
        results[job_type] = result
        print(f"   Result: {'✅ PASS' if result else '❌ FAIL'}")

        # Small delay between tests
        await asyncio.sleep(1)

    print("\n📋 Summary:")
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"   Tests passed: {passed}/{total}")

    for job_type, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   • {job_type}: {status}")

    return passed == total


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test AIBTC job deduplication")
    parser.add_argument(
        "-j",
        "--job-type",
        type=str,
        default="chain_state_monitor",
        help="Job type to test (default: chain_state_monitor)",
    )
    parser.add_argument(
        "-n",
        "--num-triggers",
        type=int,
        default=5,
        help="Number of rapid job triggers (default: 5)",
    )
    parser.add_argument(
        "-a", "--all-types", action="store_true", help="Test all monitoring job types"
    )

    args = parser.parse_args()

    async def run_tests():
        if args.all_types:
            success = await test_multiple_job_types()
        else:
            success = await test_job_deduplication(args.job_type, args.num_triggers)

        if success:
            print("\n🎉 All tests passed! Deduplication is working correctly.")
            return 0
        else:
            print("\n❌ Some tests failed. Check configuration and logs.")
            return 1

    exit_code = asyncio.run(run_tests())
    exit(exit_code)


if __name__ == "__main__":
    main()
