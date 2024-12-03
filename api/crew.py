import asyncio
import datetime
import uuid
import json
from fastapi.responses import JSONResponse
from db.helpers import add_job
from services.crews import execute_crew_stream
from tools.tools_factory import initialize_tools
from .verify_profile import verify_profile_from_token, ProfileInfo
from typing import List
from lib.models import Crew
from db.helpers import get_public_crews
from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    WebSocket,
    WebSocketDisconnect,
)
from lib.websocket_manager import manager
from logging import Logger
logger = Logger(__name__)

router = APIRouter(prefix="/crew")


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


@router.websocket("/{crew_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    crew_id: int,
    profile: ProfileInfo = Depends(verify_profile_from_token)
):
    job_id = None
    is_processing = False
    is_connected = False

    try:
        await manager.connect_job(websocket, str(crew_id))
        is_connected = True
        logger.debug(f"WebSocket connected for crew {crew_id}")
        
        while is_connected:
            try:
                # Wait for messages from the client
                data = await websocket.receive_json()
                
                # If we're still processing a job, ignore new inputs
                if is_processing:
                    await manager.send_job_message(
                        {
                            "type": "error",
                            "message": "Still processing previous request. Please wait for it to complete."
                        },
                        str(crew_id)
                    )
                    continue

                if data.get("type") == "chat_message":
                    is_processing = True
                    input_str = data.get("message", "")
                    
                    # Generate a unique job ID
                    job_id = str(uuid.uuid4())
                    results_array = []

                    # Add initial user message
                    results_array.append(
                        json.dumps({
                            "role": "user",
                            "type": "user",
                            "content": input_str,
                            "timestamp": datetime.datetime.now().isoformat()
                        })
                    )

                    try:
                        # Send job started message
                        await manager.send_job_message(
                            {
                                "type": "job_started",
                                "job_id": job_id,
                                "job_started_at": datetime.datetime.now().isoformat()
                            },
                            str(crew_id)
                        )

                        # Run the crew stream task and stream results
                        async for result in execute_crew_stream(
                            str(profile.account_index), crew_id, input_str
                        ):
                            if not is_connected:
                                break
                            result["crew_id"] = crew_id
                            result["timestamp"] = datetime.datetime.now().isoformat()
                            results_array.append(json.dumps(result))
                            await manager.send_job_message(result, str(crew_id))

                        final_result = json.loads(results_array[-1]) if results_array else None
                        final_result_content = final_result.get("content", "") if final_result else ""
        
                        add_job(
                            profile_id=profile.id,
                            conversation_id=None,
                            crew_id=crew_id,
                            input_data=input_str,
                            tokens=final_result.get("tokens", 0) if final_result else 0,
                            result=final_result_content,
                            messages=results_array
                        )

                    except Exception as e:
                        logger.error(f"Error processing crew message: {str(e)}")
                        if is_connected:
                            await manager.broadcast_job_error(str(e), str(crew_id))
                    finally:
                        is_processing = False

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for crew {crew_id}")
                is_connected = False
                break
            except json.JSONDecodeError:
                if is_connected:
                    await manager.broadcast_job_error("Invalid JSON message", str(crew_id))
            except Exception as e:
                logger.error(f"Error in WebSocket message handling: {str(e)}")
                if is_connected:
                    await manager.broadcast_job_error(str(e), str(crew_id))
                is_connected = False
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for crew {crew_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
    finally:
        is_connected = False
        await manager.disconnect_job(websocket, str(crew_id))
        logger.debug(f"Cleaned up WebSocket connection for crew {crew_id}")


@router.get("/public", response_model=List[Crew])
async def api_get_public_crews():
    try:
        crews = get_public_crews()
        return JSONResponse(content=crews)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching public crews: {str(e)}"
        )
