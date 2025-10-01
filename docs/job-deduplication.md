# Job Deduplication and Stacking Prevention

This document describes the job deduplication system implemented to prevent job stacking issues, particularly with monitoring jobs like `chain_state_monitor`.

## Problem Solved

Previously, if jobs took longer to execute than their scheduled interval, multiple instances would stack up in the queue, leading to:
- Resource waste (CPU, memory, API calls)
- Log spam
- Potential system performance degradation
- Confusing job execution patterns

## Solution Overview

The deduplication system works at two levels:

### Phase 1: JobManager Deduplication
- **Pre-scheduling checks**: Before enqueuing a job, check if similar jobs are already running or queued
- **Concurrency limits**: Respect `max_concurrent` settings per job type
- **Intelligent skipping**: Skip scheduling if limits would be exceeded

### Phase 2: Executor Deduplication  
- **Pre-enqueue deduplication**: Remove duplicate jobs before they enter the priority queue
- **Final execution check**: Last-minute check before job execution
- **Queue cleanup**: Automatic cleanup of deduplicated jobs

## Configuration

Add these environment variables to configure deduplication behavior:

```bash
# Enable/disable job deduplication (default: true)
AIBTC_JOB_DEDUPLICATION_ENABLED=true

# Enable aggressive deduplication for monitoring jobs (default: true) 
AIBTC_AGGRESSIVE_DEDUPLICATION_ENABLED=true

# Enable job stacking prevention (default: true)
AIBTC_JOB_STACKING_PREVENTION_ENABLED=true
```

### Monitoring Job Types

The following job types are treated as "monitoring jobs" with aggressive deduplication:
- `chain_state_monitor`
- `chainhook_monitor` 
- `agent_wallet_balance_monitor`
- `dao_token_holders_monitor`

These jobs will be more aggressively deduplicated since having multiple instances running simultaneously provides no benefit.

## Behavior Changes

### Before Deduplication
```
Time    Event
00:00   chain_state_monitor job scheduled
00:00   Job starts executing (takes 120 seconds)
01:30   chain_state_monitor job scheduled again
01:30   Job queued (first still running)  
03:00   chain_state_monitor job scheduled again
03:00   Job queued (first still running)
03:00   First job completes, second starts
04:30   chain_state_monitor job scheduled again  
04:30   Job queued (second still running)
...     Pattern continues, jobs stack up
```

### After Deduplication  
```
Time    Event
00:00   chain_state_monitor job scheduled
00:00   Job starts executing (takes 120 seconds)
01:30   chain_state_monitor job scheduled again
01:30   Job skipped - instance already running ✅
03:00   chain_state_monitor job scheduled again  
03:00   Job skipped - instance already running ✅
04:00   First job completes
04:30   chain_state_monitor job scheduled
04:30   Job starts executing (no conflicts) ✅
```

## Monitoring and Debugging

### Job Monitor Script

Use the job monitoring script to observe deduplication in action:

```bash
# Single snapshot
python scripts/job_monitor.py

# Continuous monitoring 
python scripts/job_monitor.py --continuous

# Monitor specific job type
python scripts/job_monitor.py --continuous --job-type chain_state_monitor
```

### Test Deduplication

Test that deduplication is working:

```bash
# Test single job type
python scripts/test_job_deduplication.py --job-type chain_state_monitor

# Test all monitoring job types
python scripts/test_job_deduplication.py --all-types
```

## Log Messages

Look for these log messages to confirm deduplication is working:

### Successful Deduplication
```
INFO | Skipping job execution - concurrency limit reached | job_type=chain_state_monitor action=skipped reason=concurrency_limit
INFO | Deduplicating monitoring job in executor | job_type=chain_state_monitor aggressive_deduplication=True  
INFO | Final execution check - skipping duplicate monitoring job | reason=concurrent_execution_detected
```

### Job Allowed
```
DEBUG | Job execution allowed | job_type=chain_state_monitor action=scheduled reason=within_limits
INFO | Scheduled job enqueued successfully | job_type=chain_state_monitor pending_count=1
```

## Configuration Tuning

### Conservative Mode
For less aggressive deduplication:
```bash
AIBTC_AGGRESSIVE_DEDUPLICATION_ENABLED=false
```

### Disable Deduplication
To completely disable (not recommended for production):
```bash
AIBTC_JOB_DEDUPLICATION_ENABLED=false
AIBTC_JOB_STACKING_PREVENTION_ENABLED=false
```

### Custom Intervals
Adjust job intervals to reduce deduplication needs:
```bash
# Increase chain_state_monitor interval to 5 minutes
AIBTC_CHAIN_STATE_MONITOR_INTERVAL_SECONDS=300
```

## Performance Impact

The deduplication system has minimal performance overhead:
- **Pre-scheduling checks**: ~1-5ms per job
- **Memory usage**: Small increase for tracking active jobs
- **CPU usage**: Negligible
- **Benefits**: Significant reduction in wasted resources

## Troubleshooting

### Jobs Not Running At All
1. Check if deduplication is too aggressive
2. Verify job configuration is correct
3. Look for errors in logs
4. Use monitoring script to check job status

### Jobs Still Stacking
1. Verify configuration environment variables are set
2. Check if job type is in monitoring list
3. Look for errors during deduplication checks
4. Test with deduplication test script

### Unexpected Behavior
1. Check job execution times vs intervals
2. Review `max_concurrent` settings
3. Monitor queue statistics
4. Check for configuration conflicts

## Future Enhancements

Potential improvements being considered:
- Dynamic interval adjustment based on execution time
- Job priority-based deduplication
- Advanced queue analytics
- Integration with monitoring systems
- Custom deduplication rules per job type
