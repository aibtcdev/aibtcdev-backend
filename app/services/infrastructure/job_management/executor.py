"""Enhanced job execution system with scalability features."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import QueueMessage, QueueMessageBase, QueueMessageFilter
from app.lib.logger import configure_logger

from .base import JobContext, JobType
from .decorators import JobMetadata, JobPriority, JobRegistry

logger = configure_logger(__name__)


class JobStatus(Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


@dataclass
class JobExecution:
    """Track individual job execution."""

    id: UUID
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    attempt: int = 1
    max_attempts: int = 3
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    retry_after: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PriorityQueue:
    """Priority-based job queue with concurrency control and deduplication."""

    def __init__(self):
        self._queues: Dict[JobPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in JobPriority
        }
        self._active_jobs: Dict[JobType, Set[UUID]] = {}
        self._semaphores: Dict[JobType, asyncio.Semaphore] = {}
        self._executions: Dict[UUID, JobExecution] = {}
        # Phase 2: Enhanced job type tracking
        self._pending_jobs_by_type: Dict[JobType, Set[UUID]] = {}
        self._job_type_locks: Dict[JobType, asyncio.Lock] = {}

    async def enqueue(
        self, message: QueueMessage, priority: JobPriority = JobPriority.NORMAL
    ) -> UUID:
        """Add a job to the priority queue with Phase 2 deduplication."""
        # Convert message type to JobType, handling both DynamicQueueMessageType and string
        type_value = (
            message.type.value if hasattr(message.type, "value") else str(message.type)
        )
        job_type = JobType.get_or_create(type_value)

        # Phase 2: Ensure we have tracking structures for this job type
        if job_type not in self._pending_jobs_by_type:
            self._pending_jobs_by_type[job_type] = set()
        if job_type not in self._job_type_locks:
            self._job_type_locks[job_type] = asyncio.Lock()

        # Phase 2: Perform deduplication before enqueuing
        if await self._should_deduplicate_job(job_type, message):
            logger.debug(
                f"Job deduplicated - not enqueuing: {str(job_type)}",
                extra={
                    "job_id": str(message.id),
                    "job_type": str(job_type),
                    "priority": str(priority),
                    "event_type": "job_deduplicated",
                },
            )
            return message.id

        execution = JobExecution(
            id=message.id, job_type=job_type, metadata={"message": message}
        )

        self._executions[message.id] = execution
        self._pending_jobs_by_type[job_type].add(message.id)
        await self._queues[priority].put(execution)

        logger.debug(
            f"Job enqueued to priority queue: {str(job_type)}",
            extra={
                "job_id": str(message.id),
                "priority": str(priority),
                "event_type": "job_enqueued",
            },
        )
        return message.id

    async def dequeue(self, priority: JobPriority) -> Optional[JobExecution]:
        """Get next job from priority queue."""
        try:
            # Try to get a job without blocking
            execution = self._queues[priority].get_nowait()
            return execution
        except asyncio.QueueEmpty:
            return None

    async def get_next_job(self) -> Optional[JobExecution]:
        """Get the next job from highest priority queue with Phase 2 final deduplication check."""
        # Check queues in priority order (highest first)
        for priority in reversed(list(JobPriority)):
            execution = await self.dequeue(priority)
            if execution:
                # Phase 2: Final deduplication check before returning job
                if await self._final_execution_check(execution):
                    # Remove from pending tracking since we're about to execute
                    self._pending_jobs_by_type[execution.job_type].discard(execution.id)
                    return execution
                else:
                    # Skip this job and clean it up
                    self._cleanup_skipped_job(execution)
                    continue
        return None

    def set_concurrency_limit(self, job_type: JobType, max_concurrent: int) -> None:
        """Set concurrency limit for a job type."""
        self._semaphores[job_type] = asyncio.Semaphore(max_concurrent)
        self._active_jobs[job_type] = set()

    async def acquire_slot(self, job_type: JobType, job_id: UUID) -> bool:
        """Acquire a concurrency slot for job execution."""
        if job_type not in self._semaphores:
            return True  # No limit set

        semaphore = self._semaphores[job_type]
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=0.1)
            self._active_jobs[job_type].add(job_id)
            return True
        except asyncio.TimeoutError:
            return False  # No slots available

    def release_slot(self, job_type: JobType, job_id: UUID) -> None:
        """Release a concurrency slot and clean up Phase 2 tracking."""
        if job_type in self._semaphores:
            self._semaphores[job_type].release()
        if job_type in self._active_jobs:
            self._active_jobs[job_type].discard(job_id)
        # Phase 2: Clean up tracking
        if job_type in self._pending_jobs_by_type:
            self._pending_jobs_by_type[job_type].discard(job_id)

    def get_execution(self, job_id: UUID) -> Optional[JobExecution]:
        """Get job execution by ID."""
        return self._executions.get(job_id)

    def update_execution(self, job_id: UUID, **kwargs) -> None:
        """Update job execution status."""
        if job_id in self._executions:
            execution = self._executions[job_id]
            for key, value in kwargs.items():
                if hasattr(execution, key):
                    setattr(execution, key, value)

    async def _should_deduplicate_job(
        self, job_type: JobType, message: QueueMessage
    ) -> bool:
        """Phase 2: Check if job should be deduplicated before enqueuing."""
        from app.config import config

        # Check if deduplication is enabled
        if not config.scheduler.job_deduplication_enabled:
            return False

        async with self._job_type_locks.get(job_type, asyncio.Lock()):
            job_type_str = str(job_type)

            # For monitoring jobs, be more aggressive with deduplication (configurable)
            if (
                config.scheduler.aggressive_deduplication_enabled
                and job_type_str in config.scheduler.monitoring_job_types
            ):
                # Check if there are any active or pending jobs of this type
                active_count = len(self._active_jobs.get(job_type, set()))
                pending_count = len(self._pending_jobs_by_type.get(job_type, set()))

                if active_count > 0 or pending_count > 0:
                    logger.info(
                        f"Deduplicating monitoring job in executor: {job_type_str}",
                        extra={
                            "active_count": active_count,
                            "pending_count": pending_count,
                            "reason": "monitoring_job_already_exists",
                            "aggressive_deduplication": True,
                            "event_type": "job_deduplicated_executor",
                        },
                    )
                    return True

            return False

    async def _final_execution_check(self, execution: JobExecution) -> bool:
        """Phase 2: Final check before executing a job."""
        from app.config import config

        job_type = execution.job_type
        job_type_str = str(job_type)

        # Skip final check if stacking prevention is disabled
        if not config.scheduler.job_stacking_prevention_enabled:
            return True

        # For monitoring jobs, do a final check to ensure we're not running duplicates
        if (
            config.scheduler.aggressive_deduplication_enabled
            and job_type_str in config.scheduler.monitoring_job_types
        ):
            active_count = len(self._active_jobs.get(job_type, set()))
            if active_count > 0:
                logger.info(
                    f"Final execution check - skipping duplicate monitoring job: {job_type_str}",
                    extra={
                        "job_id": str(execution.id),
                        "active_count": active_count,
                        "reason": "concurrent_execution_detected",
                        "aggressive_deduplication": True,
                        "stacking_prevention": config.scheduler.job_stacking_prevention_enabled,
                        "event_type": "job_execution_skipped_final_check",
                    },
                )
                return False

        return True

    def _cleanup_skipped_job(self, execution: JobExecution) -> None:
        """Phase 2: Clean up a job that was skipped."""
        job_id = execution.id
        job_type = execution.job_type

        # Remove from all tracking structures
        self._executions.pop(job_id, None)
        if job_type in self._pending_jobs_by_type:
            self._pending_jobs_by_type[job_type].discard(job_id)

        logger.debug(
            f"Cleaned up skipped job: {str(job_type)}",
            extra={
                "job_id": str(job_id),
                "event_type": "job_cleanup",
            },
        )

    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Phase 2: Get deduplication statistics."""
        from app.config import config

        return {
            "pending_jobs_by_type": {
                str(job_type): len(job_ids)
                for job_type, job_ids in self._pending_jobs_by_type.items()
            },
            "active_jobs_by_type": {
                str(job_type): len(job_ids)
                for job_type, job_ids in self._active_jobs.items()
            },
            "total_pending_jobs": sum(
                len(jobs) for jobs in self._pending_jobs_by_type.values()
            ),
            "total_active_jobs": sum(len(jobs) for jobs in self._active_jobs.values()),
            "config": {
                "deduplication_enabled": config.scheduler.job_deduplication_enabled,
                "aggressive_deduplication": config.scheduler.aggressive_deduplication_enabled,
                "stacking_prevention": config.scheduler.job_stacking_prevention_enabled,
                "monitoring_job_types": config.scheduler.monitoring_job_types,
            },
        }


class RetryManager:
    """Manages job retry logic with exponential backoff."""

    @staticmethod
    def should_retry(execution: JobExecution, metadata: JobMetadata) -> bool:
        """Determine if a job should be retried."""
        if execution.attempt >= metadata.max_retries:
            return False

        # Check if enough time has passed for retry
        if execution.retry_after and datetime.now() < execution.retry_after:
            return False

        return True

    @staticmethod
    def calculate_retry_delay(
        attempt: int, base_delay: int = 30, max_delay: int = 3600
    ) -> int:
        """Calculate retry delay with exponential backoff."""
        delay = base_delay * (2 ** (attempt - 1))
        return min(delay, max_delay)

    @staticmethod
    def schedule_retry(execution: JobExecution, metadata: JobMetadata) -> None:
        """Schedule a job for retry."""
        delay = RetryManager.calculate_retry_delay(
            execution.attempt, metadata.retry_delay_seconds
        )
        execution.retry_after = datetime.now() + timedelta(seconds=delay)
        execution.status = JobStatus.RETRYING
        execution.attempt += 1

        logger.info(
            f"Job scheduled for retry: {str(execution.job_type)}",
            extra={
                "job_id": str(execution.id),
                "attempt": execution.attempt,
                "retry_delay_seconds": delay,
                "event_type": "job_retry_scheduled",
            },
        )


class DeadLetterQueue:
    """Handles jobs that have failed all retry attempts."""

    def __init__(self):
        self._dead_jobs: Dict[UUID, JobExecution] = {}

    def add_dead_job(self, execution: JobExecution) -> None:
        """Add a job to the dead letter queue."""
        execution.status = JobStatus.DEAD_LETTER
        execution.completed_at = datetime.now()
        self._dead_jobs[execution.id] = execution

        logger.error(
            f"Job moved to dead letter queue: {str(execution.job_type)}",
            extra={
                "job_id": str(execution.id),
                "attempts": execution.attempt,
                "error": execution.error,
                "event_type": "job_dead_letter",
            },
        )

    def get_dead_jobs(self) -> List[JobExecution]:
        """Get all jobs in the dead letter queue."""
        return list(self._dead_jobs.values())

    def remove_dead_job(self, job_id: UUID) -> Optional[JobExecution]:
        """Remove a job from the dead letter queue."""
        return self._dead_jobs.pop(job_id, None)


class JobExecutor:
    """Enhanced job executor with scalability features and job completion tracking."""

    def __init__(self):
        self.priority_queue = PriorityQueue()
        self.retry_manager = RetryManager()
        self.dead_letter_queue = DeadLetterQueue()
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        # Phase 2: Job completion callback for cleanup
        self._job_completion_callback = None

    async def start(self, num_workers: int = 5) -> None:
        """Start the job executor with specified number of workers."""
        if self._running:
            logger.warning(
                "JobExecutor is already running",
                extra={"event_type": "executor_already_running"},
            )
            return

        self._running = True

        # Initialize concurrency limits from job metadata
        for job_type, metadata in JobRegistry.list_jobs().items():
            self.priority_queue.set_concurrency_limit(job_type, metadata.max_concurrent)

        # Start worker tasks
        for i in range(num_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(task)

        logger.info(
            "JobExecutor started",
            extra={"worker_count": num_workers, "event_type": "executor_started"},
        )

    async def stop(self) -> None:
        """Stop the job executor."""
        if not self._running:
            return

        self._running = False

        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        self._worker_tasks.clear()
        logger.info("JobExecutor stopped", extra={"event_type": "executor_stopped"})

    async def _worker(self, worker_name: str) -> None:
        """Worker coroutine that processes jobs from the queue."""
        logger.debug(
            f"Worker starting: {worker_name}",
            extra={"event_type": "worker_start"},
        )

        while self._running:
            try:
                # Get next job from priority queue
                execution = await self.priority_queue.get_next_job()
                if not execution:
                    await asyncio.sleep(
                        0.5
                    )  # Increased pause if no jobs to reduce CPU usage
                    continue

                # Check if we can acquire a slot for this job type
                acquired = await self.priority_queue.acquire_slot(
                    execution.job_type, execution.id
                )
                if not acquired:
                    # Put job back in queue and try later
                    metadata = JobRegistry.get_metadata(execution.job_type)
                    if metadata:
                        await self.priority_queue.enqueue(
                            execution.metadata["message"], metadata.priority
                        )
                    await asyncio.sleep(0.5)
                    continue

                # Execute the job
                try:
                    await self._execute_job(execution, worker_name)
                finally:
                    # Always release the slot
                    self.priority_queue.release_slot(execution.job_type, execution.id)

            except Exception as e:
                logger.error(
                    f"Worker encountered error: {worker_name}",
                    extra={
                        "error": str(e),
                        "event_type": "worker_error",
                    },
                    exc_info=True,
                )
                await asyncio.sleep(1)  # Pause on error

    async def _execute_job(self, execution: JobExecution, worker_name: str) -> None:
        """Execute a single job."""
        job_id = execution.id
        job_type = execution.job_type
        start_time = time.time()

        logger.debug(
            f"Job execution started: {worker_name}",
            extra={
                "job_id": str(job_id),
                "job_type": str(job_type),
                "event_type": "job_execution_start",
            },
        )

        # Record execution start in metrics
        from .monitoring import get_metrics_collector

        metrics = get_metrics_collector()
        metrics.record_execution_start(execution, worker_name)

        # Update execution status
        self.priority_queue.update_execution(
            job_id, status=JobStatus.RUNNING, started_at=datetime.now()
        )

        try:
            # Get job metadata and task instance
            metadata = JobRegistry.get_metadata(job_type)
            task_instance = JobRegistry.get_instance(job_type)

            if not metadata or not task_instance:
                raise ValueError(f"Job type {job_type} not properly registered")

            # Create job context
            from .base import RunnerConfig

            context = JobContext(
                job_type=job_type,
                config=RunnerConfig(),
                retry_count=execution.attempt - 1,
                max_retries=metadata.max_retries,
            )

            # Execute the task with timeout
            if metadata.timeout_seconds:
                results = await asyncio.wait_for(
                    task_instance.execute(context), timeout=metadata.timeout_seconds
                )
            else:
                results = await task_instance.execute(context)

            # Calculate execution duration
            duration = time.time() - start_time

            # Update execution with results
            self.priority_queue.update_execution(
                job_id,
                status=JobStatus.COMPLETED,
                completed_at=datetime.now(),
                result=results,
            )

            # Record successful execution in metrics
            metrics.record_execution_completion(execution, duration)

            # Mark message as processed in database
            message = execution.metadata["message"]
            backend.update_queue_message(
                queue_message_id=message.id,
                update_data=QueueMessageBase(is_processed=True),
            )

            # Phase 2: Notify job manager of completion for cleanup
            if self._job_completion_callback:
                try:
                    job_type_str = str(job_type)
                    self._job_completion_callback(
                        job_type_str, job_id, True
                    )  # True for success
                except Exception as callback_error:
                    logger.warning(
                        f"Job completion callback failed: {str(job_type)}",
                        extra={
                            "job_id": str(job_id),
                            "callback_error": str(callback_error),
                            "event_type": "callback_error",
                        },
                    )

            logger.info(
                f"Job completed successfully: {worker_name}, {job_type}",
                extra={
                    "job_id": str(job_id),
                    "duration_seconds": round(duration, 2),
                    "event_type": "job_completed",
                },
            )

        except Exception as e:
            error_msg = str(e)
            duration = time.time() - start_time

            logger.error(
                "Job execution failed: {worker_name}, {job_type}",
                extra={
                    "job_id": str(job_id),
                    "duration_seconds": round(duration, 2),
                    "error": error_msg,
                    "event_type": "job_failed",
                },
            )

            # Record failed execution in metrics
            metrics.record_execution_failure(execution, error_msg, duration)

            # Update execution with error
            self.priority_queue.update_execution(
                job_id, status=JobStatus.FAILED, error=error_msg
            )

            # Handle retry or dead letter
            metadata = JobRegistry.get_metadata(job_type)
            if metadata and self.retry_manager.should_retry(execution, metadata):
                metrics.record_execution_retry(execution)
                self.retry_manager.schedule_retry(execution, metadata)
                # Re-enqueue for retry
                message = execution.metadata["message"]
                await self.priority_queue.enqueue(message, metadata.priority)
            else:
                # Move to dead letter queue
                metrics.record_dead_letter(execution)
                self.dead_letter_queue.add_dead_job(execution)

                # Phase 2: Notify job manager of failure for cleanup
                if self._job_completion_callback:
                    try:
                        job_type_str = str(job_type)
                        self._job_completion_callback(
                            job_type_str, job_id, False
                        )  # False for failure
                    except Exception as callback_error:
                        logger.warning(
                            f"Job completion callback failed: {job_type}",
                            extra={
                                "job_id": str(job_id),
                                "callback_error": str(callback_error),
                                "event_type": "callback_error",
                            },
                        )

    async def enqueue_pending_jobs(self) -> int:
        """Load pending jobs from database and enqueue them."""
        enqueued_count = 0

        for job_type, metadata in JobRegistry.list_enabled_jobs().items():
            try:
                # Get pending messages for this job type
                filters = QueueMessageFilter(type=job_type.value, is_processed=False)
                pending_messages = backend.list_queue_messages(filters=filters)

                # Enqueue each message
                for message in pending_messages:
                    await self.priority_queue.enqueue(message, metadata.priority)
                    enqueued_count += 1

                if pending_messages:
                    logger.debug(
                        f"{len(pending_messages)} Pending jobs enqueued: {str(job_type)}",
                        extra={
                            "event_type": "pending_jobs_enqueued",
                        },
                    )

            except Exception as e:
                logger.error(
                    f"Error enqueuing pending jobs: {str(job_type)}",
                    extra={
                        "error": str(e),
                        "event_type": "enqueue_error",
                    },
                    exc_info=True,
                )

        if enqueued_count > 0:
            logger.info(
                "{enqueued_count} Pending jobs enqueue complete",
                extra={
                    "event_type": "pending_jobs_complete",
                },
            )

        return enqueued_count

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics including Phase 2 deduplication info."""
        dedup_stats = self.priority_queue.get_deduplication_stats()
        stats = {
            "running": self._running,
            "worker_count": len(self._worker_tasks),
            "dead_letter_count": len(self.dead_letter_queue.get_dead_jobs()),
            "active_jobs": dedup_stats["active_jobs_by_type"],
            "pending_jobs": dedup_stats["pending_jobs_by_type"],
            "total_pending": dedup_stats["total_pending_jobs"],
            "total_active": dedup_stats["total_active_jobs"],
        }
        return stats

    def set_job_completion_callback(self, callback) -> None:
        """Phase 2: Set callback function to be called when jobs complete."""
        self._job_completion_callback = callback


# Global executor instance
_executor: Optional[JobExecutor] = None
# Phase 2: Global job manager reference for callbacks
_job_manager_callback = None


def set_job_manager_callback(callback) -> None:
    """Phase 2: Set the job manager callback for cleanup notifications."""
    global _job_manager_callback
    _job_manager_callback = callback

    # Update existing executor if it exists
    global _executor
    if _executor:

        def job_completion_callback(job_type: str, job_id, success: bool):
            if _job_manager_callback:
                _job_manager_callback(job_type)

        _executor.set_job_completion_callback(job_completion_callback)


def get_executor() -> JobExecutor:
    """Get the global job executor instance."""
    global _executor
    if _executor is None:
        _executor = JobExecutor()
        # Phase 2: Setup job completion callback when first created
        _setup_job_completion_callback(_executor)
    return _executor


def _setup_job_completion_callback(executor: JobExecutor) -> None:
    """Phase 2: Setup the job completion callback to notify job manager."""

    def job_completion_callback(job_type: str, job_id, success: bool):
        """Callback to notify job manager of job completion."""
        # We'll need to get the global job manager instance
        # This will be set up when the job manager calls set_executor_callback
        pass

    executor.set_job_completion_callback(job_completion_callback)
