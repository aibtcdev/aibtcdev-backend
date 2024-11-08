import asyncio
import datetime
import uuid
import json
from fastapi.responses import JSONResponse, StreamingResponse
from services.crew_services import execute_crew_stream
from tools.tools_factory import initialize_tools
from .verify_profile import verify_profile, ProfileInfo
from db.supabase_client import supabase
from cachetools import TTLCache
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    Response,
    Depends,
    Body,
)


router = APIRouter()

running_tasks = {}

# Set up TTLCache with a max size and a time-to-live (TTL)
connection_tokens = TTLCache(maxsize=1000, ttl=3600)


async def create_connection_token(profile: ProfileInfo):
    token = str(uuid.uuid4())
    connection_tokens[token] = {
        "profile_id": profile.id,
        "account_index": profile.account_index,
    }
    return token


@router.get("/tools")
async def get_avaliable_tools():
    try:
        tools_map = initialize_tools("0")
        response = {
            tool_name: tool_instance.description
            for tool_name, tool_instance in tools_map.items()
        }

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@router.post("/new")
async def get_connection_token(
    profile: ProfileInfo = Depends(verify_profile),
):
    token = await create_connection_token(profile)
    return JSONResponse(content={"connection_token": token})


@router.get("/sse")
async def sse_streaming(
    task_id: str = Query(...),  # Require task_id as a query parameter
):
    task_info = running_tasks.get(task_id)
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


@router.post("/execute_crew/{crew_id}")
async def execute_crew_endpoint(
    crew_id: int,
    input_str: str = Body(...),
    profile: ProfileInfo = Depends(verify_profile),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    output_queue = asyncio.Queue()
    results_array = []

    async def task_wrapper():
        try:
            # Run the actual crew stream task, yielding output to the queue
            async for result in execute_crew_stream(
                str(profile.account_index), crew_id, input_str
            ):
                await output_queue.put(result)  # Put each result in the queue
                result["crew_id"] = crew_id  # Add crew_id to each result
                result["timestamp"] = datetime.datetime.now().isoformat()
                print(result)
                results_array.append(json.dumps(result))
            await output_queue.put(None)  # Signal completion
        finally:
            # i need to store the messages in the output queue in supabase db
            update_message(profile, results_array)

            running_tasks.pop(
                task_id, None
            )  # Remove task from the dictionary when done

    # Create and store the task with its output queue
    task = asyncio.create_task(task_wrapper())
    running_tasks[task_id] = {"task": task, "queue": output_queue}
    background_tasks.add_task(task_wrapper)

    # Return the task ID immediately
    return JSONResponse(content={"task_id": task_id})


def update_message(profile, messages):
    # Update the message in the database
    response = (
        supabase.table("conversations")
        .select("*")
        .eq("profile_id", profile.id)
        .execute()
    )
    data = response.data

    if data:
        # Conversation exists, so append to the existing messages
        conversation_id = data[0]["id"]
        existing_messages = data[0]["messages"]

        # Append the new message to the messages array
        updated_messages = existing_messages + messages

        # Update the conversation with the appended messages
        supabase.table("conversations").update({"messages": updated_messages}).eq(
            "id", conversation_id
        ).execute()

    else:
        # No conversation exists, create a new one
        new_conversation = {
            "profile_id": profile.id,
            "messages": messages,
        }
        supabase.table("conversations").insert(new_conversation).execute()


@router.get("/history")
async def history(
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        # Retrieve existing conversation for the user if it exists
        response = (
            supabase.table("conversations")
            .select("*")
            .eq("profile_id", profile.id)
            .execute()
        )
        data = response.data

        if data:
            # Conversation exists
            conversation_id = data[0]["id"]
            existing_messages = data[0]["messages"]

            return JSONResponse(
                content={
                    "id": conversation_id,
                    "messages": list(map(lambda x: json.loads(x), existing_messages)),
                }
            )

        else:
            # No conversation exists, create a new one
            new_conversation = {
                "profile_id": profile.id,
                "messages": [],
            }
            supabase.table("conversations").insert(new_conversation).execute()

        return JSONResponse(content={"status": "Message stored successfully"})

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to store message: {str(e)}"
        )


# Endpoint to cancel a background task given its task_id
@router.post("/cancel_task/{task_id}")
async def cancel_task(task_id: str):
    task_info = running_tasks.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_info["task"]

    # Cancel the task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return {"message": "Task cancelled successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error while cancelling task: {str(e)}"
        )

    return JSONResponse(content={"message": "Task cancelled successfully"})
