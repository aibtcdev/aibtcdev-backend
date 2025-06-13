"""Enhanced job execution system with scalability features."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from backend.factory import backend
from backend.models import QueueMessage, QueueMessageBase, QueueMessageFilter
from lib.logger import configure_logger

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
    """Priority-based job queue with concurrency control."""

    def __init__(self):
        self._queues: Dict[JobPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in JobPriority
        }
        self._active_jobs: Dict[JobType, Set[UUID]] = {}
        self._semaphores: Dict[JobType, asyncio.Semaphore] = {}
        self._executions: Dict[UUID, JobExecution] = {}

    async def enqueue(
        self, message: QueueMessage, priority: JobPriority = JobPriority.NORMAL
    ) -> UUID:
        """Add a job to the priority queue."""
        # Convert message type to JobType, handling both DynamicQueueMessageType and string
        type_value = (
            message.type.value if hasattr(message.type, "value") else str(message.type)
        )
        job_type = JobType.get_or_create(type_value)
        execution = JobExecution(
            id=message.id, job_type=job_type, metadata={"message": message}
        )

        self._executions[message.id] = execution
        await self._queues[priority].put(execution)

        logger.debug(f"Enqueued job {message.id} with priority {priority}")
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
        """Get the next job from highest priority queue."""
        # Check queues in priority order (highest first)
        for priority in reversed(list(JobPriority)):
            execution = await self.dequeue(priority)
            if execution:
                return execution
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
        """Release a concurrency slot."""
        if job_type in self._semaphores:
            self._semaphores[job_type].release()
        if job_type in self._active_jobs:
            self._active_jobs[job_type].discard(job_id)

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
            f"Scheduling retry for job {execution.id} "
            f"(attempt {execution.attempt}) in {delay} seconds"
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
            f"Job {execution.id} moved to dead letter queue after "
            f"{execution.attempt} attempts. Error: {execution.error}"
        )

    def get_dead_jobs(self) -> List[JobExecution]:
        """Get all jobs in the dead letter queue."""
        return list(self._dead_jobs.values())

    def remove_dead_job(self, job_id: UUID) -> Optional[JobExecution]:
        """Remove a job from the dead letter queue."""
        return self._dead_jobs.pop(job_id, None)


class JobExecutor:
    """Enhanced job executor with scalability features."""

    def __init__(self):
        self.priority_queue = PriorityQueue()
        self.retry_manager = RetryManager()
        self.dead_letter_queue = DeadLetterQueue()
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []

    async def start(self, num_workers: int = 5) -> None:
        """Start the job executor with specified number of workers."""
        if self._running:
            logger.warning("JobExecutor is already running")
            return

        self._running = True

        # Initialize concurrency limits from job metadata
        for job_type, metadata in JobRegistry.list_jobs().items():
            self.priority_queue.set_concurrency_limit(job_type, metadata.max_concurrent)

        # Start worker tasks
        for i in range(num_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(task)

        logger.info(f"Started JobExecutor with {num_workers} workers")

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
        logger.info("Stopped JobExecutor")

    async def _worker(self, worker_name: str) -> None:
        """Worker coroutine that processes jobs from the queue."""
        logger.debug(f"Starting worker: {worker_name}")

        while self._running:
            try:
                # Get next job from priority queue
                execution = await self.priority_queue.get_next_job()
                if not execution:
                    await asyncio.sleep(0.1)  # Brief pause if no jobs
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
                logger.error(f"Worker {worker_name} error: {str(e)}", exc_info=True)
                await asyncio.sleep(1)  # Pause on error

    async def _execute_job(self, execution: JobExecution, worker_name: str) -> None:
        """Execute a single job."""
        job_id = execution.id
        job_type = execution.job_type
        start_time = time.time()

        logger.debug(f"{worker_name} executing job {job_id} ({job_type})")

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
                config=RunnerConfig.from_env(),
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

            logger.info(f"{worker_name} completed job {job_id} in {duration:.2f}s")

        except Exception as e:
            error_msg = str(e)
            duration = time.time() - start_time

            logger.error(f"{worker_name} job {job_id} failed: {error_msg}")

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
                    logger.debug(f"Enqueued {len(pending_messages)} {job_type} jobs")

            except Exception as e:
                logger.error(
                    f"Error enqueuing jobs for {job_type}: {str(e)}", exc_info=True
                )

        if enqueued_count > 0:
            logger.info(f"Enqueued {enqueued_count} pending jobs")

        return enqueued_count

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        stats = {
            "running": self._running,
            "worker_count": len(self._worker_tasks),
            "dead_letter_count": len(self.dead_letter_queue.get_dead_jobs()),
            "active_jobs": {
                str(job_type): len(jobs)
                for job_type, jobs in self.priority_queue._active_jobs.items()
            },
        }
        return stats


# Global executor instance
_executor: Optional[JobExecutor] = None


def get_executor() -> JobExecutor:
    """Get the global job executor instance."""
    global _executor
    if _executor is None:
        _executor = JobExecutor()
    return _executor
