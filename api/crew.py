import asyncio
import datetime
import uuid
import json
from fastapi.responses import JSONResponse, StreamingResponse
from db.helpers import add_job
from services.crew_services import execute_crew_stream
from tools.tools_factory import initialize_tools
from .verify_profile import verify_profile, ProfileInfo
from typing import List
from lib.models import Crew
from db.helpers import get_public_crews
from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Body,
)


router = APIRouter(prefix="/crew")

running_jobs = {}


@router.get("/public", response_model=List[Crew])
async def public_crews():
    try:
        response = get_public_crews()
        return JSONResponse(content=response)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching public crews: {str(e)}"
        )


@router.get("/tools")
async def get_avaliable_tools():
    try:
        tools_map = initialize_tools("0")
        response = {
            tool_name: tool_instance.description
            for tool_name, tool_instance in tools_map.items()
        }
        return JSONResponse(content=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@router.post("/{crew_id}")
async def execute_crew_endpoint(
    crew_id: int,
    input_str: str = Body(...),
    profile: ProfileInfo = Depends(verify_profile),
):
    # Generate a unique task ID
    job_id = str(uuid.uuid4())
    output_queue = asyncio.Queue()
    results_array = []

    results_array.append(
        json.dumps(
            {
                "role": "user",
                "type": "user",
                "content": input_str,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )
    )

    async def task_wrapper():
        try:
            # Run the actual crew stream task, yielding output to the queue
            async for result in execute_crew_stream(
                str(profile.account_index), crew_id, input_str
            ):
                await output_queue.put(result)
                result["crew_id"] = crew_id
                result["timestamp"] = datetime.datetime.now().isoformat()
                results_array.append(json.dumps(result))
            await output_queue.put(None)  # Signal completion
        finally:
            add_job(
                profile,
                None,
                crew_id,
                input_str,
                "",
                results_array,
            )
            running_jobs.pop(job_id, None)

    task = asyncio.create_task(task_wrapper())
    running_jobs[job_id] = {
        "task": task,
        "queue": output_queue,
        "profile": profile,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # Return the task ID immediately
    return JSONResponse(content={"job_id": job_id})


# Endpoint to get all background tasks for a given profile
@router.get("/jobs")
async def get_all_background_tasks(profile: ProfileInfo = Depends(verify_profile)):
    tasks = []
    for job_id, task_info in running_jobs.items():
        if task_info["profile"].id == profile.id:
            task = {
                "job_id": job_id,
                "timestamp": task_info["timestamp"],
            }
            tasks.append(task)
    return JSONResponse(content=tasks)


@router.get("/jobs/{job_id}/stream")
async def sse_streaming(job_id: str):
    task_info = running_jobs.get(job_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    output_queue = task_info["queue"]

    async def event_generator():
        try:
            while True:
                # Retrieve data from the queue
                result = await output_queue.get()
                if result is None:  # Task completed
                    break
                # Yield the result as JSON for SSE
                json_result = json.dumps(result)
                yield f"data: {json_result}\n\n"
        except Exception as e:
            error_message = json.dumps({"error": f"Execution error: {str(e)}"})
            yield f"data: {error_message}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Endpoint to cancel a background task given its job_id
@router.delete("/jobs/{job_id}/cancel")
async def cancel_task(
    job_id: str,
    profile: ProfileInfo = Depends(verify_profile),
):
    task_info = running_jobs.get(job_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_info["profile"].id != profile.id:
        raise HTTPException(
            status_code=403, detail="You do not have permission to cancel this task."
        )

    task = task_info["task"]

    # Cancel the task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return JSONResponse(content={"message": "Task cancelled successfully"})
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error while cancelling task: {str(e)}"
        )

    return JSONResponse(content={"message": "Task cancelled successfully"})
