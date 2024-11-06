from typing import Any, Dict
import uuid
from cachetools import TTLCache
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Response,
    Depends,
    Body,
)
from fastapi.responses import JSONResponse, StreamingResponse
from services.crew_services import execute_crew, execute_crew_stream
from tools.tools_factory import initialize_tools
from .verify_profile import verify_profile

router = APIRouter()

# Set up TTLCache with a max size and a time-to-live (TTL) of 5 minutes (300 seconds)
connection_tokens = TTLCache(maxsize=1000, ttl=300)


async def create_connection_token(account_index: int, request_data: Dict[str, Any]):
    token = str(uuid.uuid4())
    # Store token with the request data and account_index in TTLCache
    connection_tokens[token] = {"account_index": account_index, "data": request_data}
    return token


@router.post("/execute_crew/{crew_id}")
async def execute_crew_endpoint(
    crew_id: int,
    input_str: str = Body(...),
    account_index: str = Depends(verify_profile),
):
    try:
        # Execute the crew logic with the provided input string
        result = execute_crew(str(account_index), crew_id, input_str)

        return {"result": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@router.post("/new")
async def get_connection_token(
    account_index: int = Depends(verify_profile),
    request_data: str = Body(...),
):
    token = await create_connection_token(account_index, request_data)
    return JSONResponse(content={"connection_token": token})


@router.get("/sse/execute_crew/{crew_id}")
async def sse_execute_crew(
    crew_id: int,
    connection_token: str = Query(...),  # Require token as a query parameter
):
    # Verify and retrieve token data from TTLCache
    token_data = connection_tokens.get(connection_token)
    if not token_data:
        raise HTTPException(
            status_code=403, detail="Invalid or missing connection token"
        )

    # Extract account_index and request data from the token data
    account_index = token_data["account_index"]
    request_data = token_data["data"]

    async def event_generator():
        try:
            # Use account_index and request_data with execute_crew_stream
            async for result in execute_crew_stream(
                account_index, crew_id, request_data
            ):
                yield f"data: {result}\n\n"
        except Exception as e:
            yield f"data: Execution error: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
