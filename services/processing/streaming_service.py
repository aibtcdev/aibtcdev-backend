import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, TypedDict
from uuid import UUID

from lib.logger import configure_logger

logger = configure_logger(__name__)


class JobInfo(TypedDict):
    """Information about a running job."""

    queue: asyncio.Queue
    thread_id: UUID
    agent_id: Optional[UUID]
    task: Optional[asyncio.Task]
    connection_active: bool


# Global job tracking
thread_pool = ThreadPoolExecutor()
running_jobs: Dict[str, JobInfo] = {}


async def mark_jobs_disconnected_for_session(session_id: str) -> None:
    """Mark all running jobs associated with a session as disconnected.

    Args:
        session_id: The session ID to mark jobs for
    """
    disconnected_count = 0
    for job_id, job_info in running_jobs.items():
        if job_info.get("task") and job_info.get("connection_active", True):
            logger.info(
                f"Marking job {job_id} as disconnected due to WebSocket disconnect for session {session_id}"
            )
            job_info["connection_active"] = False
            disconnected_count += 1

    if disconnected_count > 0:
        logger.info(
            f"Marked {disconnected_count} jobs as disconnected for session {session_id}"
        )
    else:
        logger.debug(f"No active jobs found for session {session_id}")
