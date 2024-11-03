from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    Body,
)
from services.crew_services import execute_crew, execute_crew_stream
from tools.tools_factory import initialize_tools
from .verify_profile import verify_profile

router = APIRouter()


@router.post("/execute_crew/{crew_id}")
async def execute_crew_endpoint(
    crew_id: int,
    input_str: str = Body(...),
    account_index: str = Depends(verify_profile),
):
    try:
        # Execute the crew logic with the provided input string
        result = execute_crew(account_index, crew_id, input_str)

        return {"result": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@router.websocket("/ws/execute_crew/{crew_id}")
async def websocket_execute_crew(
    websocket: WebSocket,
    crew_id: int,
    account_index: int = Depends(verify_profile),
):
    await websocket.accept()
    try:
        # Receive the input string from the client
        input_str = await websocket.receive_text()

        # Execute the crew logic with the provided input string
        async for result in execute_crew_stream(account_index, crew_id, input_str):
            await websocket.send_json(result)

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_text(f"Execution error: {str(e)}")
        await websocket.close()


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
