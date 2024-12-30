import datetime
import json
import uuid
from .verify_profile import ProfileInfo, verify_profile_from_token
from db.factory import db
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from lib.logger import configure_logger
from lib.websocket_manager import manager
from services.crews import execute_crew_stream
from tools.tools_factory import initialize_tools
from typing import Dict

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/crew")


@router.websocket("/{crew_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    crew_id: int,
    profile: ProfileInfo = Depends(verify_profile_from_token),
) -> None:
    """Handle WebSocket connections for crew interactions.

    This endpoint manages real-time communication between the client and crew,
    processing chat messages and streaming responses.

    Args:
        websocket (WebSocket): The WebSocket connection
        crew_id (int): ID of the crew to interact with
        profile (ProfileInfo): User profile information from token verification

    Note:
        The connection will remain open until explicitly closed or an error occurs.
        Messages are processed one at a time to prevent overlapping operations.
    """
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
                logger.debug(
                    f"Received message for crew {crew_id}: {data.get('type', 'unknown_type')}"
                )

                # If we're still processing a job, ignore new inputs
                if is_processing:
                    logger.warning(
                        f"Ignoring new message for crew {crew_id} - still processing previous request"
                    )
                    await manager.send_job_message(
                        {
                            "type": "error",
                            "message": "Still processing previous request. Please wait for it to complete.",
                        },
                        str(crew_id),
                    )
                    continue

                if data.get("type") == "chat_message":
                    is_processing = True
                    input_str = data.get("message", "")
                    logger.info(f"Processing chat message for crew {crew_id}")

                    # Generate a unique job ID
                    job_id = str(uuid.uuid4())
                    results_array = []

                    # Add initial user message
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

                    try:
                        # Send job started message
                        logger.debug(f"Starting job {job_id} for crew {crew_id}")
                        await manager.send_job_message(
                            {
                                "type": "job_started",
                                "job_id": job_id,
                                "job_started_at": datetime.datetime.now().isoformat(),
                            },
                            str(crew_id),
                        )

                        # Run the crew stream task and stream results
                        logger.debug(f"Executing crew stream for job {job_id}")
                        async for result in execute_crew_stream(
                            profile, crew_id, input_str
                        ):
                            if not is_connected:
                                logger.warning(
                                    f"Connection lost while streaming results for job {job_id}"
                                )
                                break
                            result["crew_id"] = crew_id
                            result["timestamp"] = datetime.datetime.now().isoformat()
                            results_array.append(json.dumps(result))
                            await manager.send_job_message(result, str(crew_id))

                        final_result = (
                            json.loads(results_array[-1]) if results_array else None
                        )
                        final_result_content = (
                            final_result.get("content", "") if final_result else ""
                        )

                        logger.debug(f"Saving job {job_id} results to database")
                        db.add_job(
                            profile_id=profile.id,
                            conversation_id=None,
                            crew_id=crew_id,
                            input_data=input_str,
                            tokens=final_result.get("tokens", 0) if final_result else 0,
                            result=final_result_content,
                            messages=results_array,
                        )
                        logger.info(
                            f"Successfully completed job {job_id} for crew {crew_id}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error processing crew message for job {job_id}: {str(e)}",
                            exc_info=True,
                        )
                        if is_connected:
                            await manager.broadcast_job_error(str(e), str(crew_id))
                    finally:
                        is_processing = False

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for crew {crew_id}")
                is_connected = False
                break
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON message for crew {crew_id}")
                if is_connected:
                    await manager.broadcast_job_error(
                        "Invalid JSON message", str(crew_id)
                    )
            except Exception as e:
                logger.error(
                    f"Error in WebSocket message handling for crew {crew_id}: {str(e)}",
                    exc_info=True,
                )
                if is_connected:
                    await manager.broadcast_job_error(str(e), str(crew_id))
                is_connected = False
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for crew {crew_id}")
    except Exception as e:
        logger.error(
            f"Error in WebSocket connection for crew {crew_id}: {str(e)}", exc_info=True
        )
    finally:
        is_connected = False
        await manager.disconnect_job(websocket, str(crew_id))
        logger.debug(f"Cleaned up WebSocket connection for crew {crew_id}")


@router.get("/tools")
async def get_avaliable_tools() -> Dict[str, str]:
    """Get a list of available tools and their descriptions.

    Returns:
        Dict[str, str]: Dictionary mapping tool names to their descriptions

    Raises:
        HTTPException: If there's an error initializing or fetching tools
    """
    logger.debug("Fetching available tools")
    try:
        profile = ProfileInfo(account_index="", id=0)
        tools_map = initialize_tools(profile)
        response = {
            tool_name: tool_instance.description
            for tool_name, tool_instance in tools_map.items()
        }
        logger.debug(f"Successfully retrieved {len(response)} tools")
        return JSONResponse(content=response)
    except Exception as e:
        logger.error(f"Error fetching available tools: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
