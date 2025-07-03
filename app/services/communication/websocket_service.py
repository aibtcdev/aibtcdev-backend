import asyncio
import datetime
import time
from typing import Any, Dict, Optional

from fastapi import WebSocket

from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class WebSocketConnection:
    """Represents a single WebSocket connection with metadata."""

    def __init__(self, websocket: WebSocket, created_at: float = None):
        self.websocket = websocket
        self.created_at = created_at or time.time()
        self.is_closed = False
        self.accepted = (
            True  # We assume websocket is already accepted when added to manager
        )
        self.metadata: Dict[str, Any] = {}

    def is_connected(self) -> bool:
        """Check if the WebSocket is still connected."""
        if self.is_closed:
            return False

        # Check WebSocket state
        try:
            # Check if the connection was properly accepted
            if not self.accepted:
                logger.debug("WebSocket was not properly accepted")
                self.is_closed = True
                return False

            # This is a heuristic - if the client is in a DISCONNECTED state,
            # we consider the connection closed
            if hasattr(self.websocket, "client_state") and getattr(
                self.websocket, "client_state", None
            ) == getattr(self.websocket, "DISCONNECTED", None):
                logger.debug("WebSocket in DISCONNECTED state")
                self.is_closed = True
                return False

            # Check if the socket has a socket attribute (depends on ASGI implementation)
            if hasattr(self.websocket, "socket") and not self.websocket.socket:
                logger.debug("WebSocket socket attribute is None")
                self.is_closed = True
                return False
        except Exception as e:
            # Any exception when checking state means it's not usable
            logger.debug(f"Exception when checking WebSocket state: {e}")
            self.is_closed = True
            return False

        return True

    async def send_message(self, message: dict) -> bool:
        """Safely send a message through this connection.

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.is_connected():
            logger.debug("WebSocket is not connected, skipping message")
            return False

        try:
            # Set a timeout for sending the message
            await asyncio.wait_for(self.websocket.send_json(message), timeout=1.0)
            return True
        except (asyncio.TimeoutError, RuntimeError) as e:
            logger.debug(f"Timeout or runtime error sending message: {e}")
            self.is_closed = True
            return False
        except Exception as e:
            # Check for the specific "need to call accept first" error
            if "accept" in str(e).lower():
                logger.debug(
                    "WebSocket was not accepted before sending. Marking as closed."
                )
                self.is_closed = True
                self.accepted = False
            else:
                logger.debug(f"Error sending message: {type(e).__name__}: {e}")
                self.is_closed = True
            return False

    async def close(self) -> None:
        """Safely close this WebSocket connection."""
        if self.is_closed:
            return

        try:
            await asyncio.wait_for(self.websocket.close(), timeout=0.5)
        except asyncio.TimeoutError:
            logger.debug("Timeout closing WebSocket")
        except Exception as e:
            logger.debug(f"Error closing WebSocket: {type(e).__name__}: {e}")
        finally:
            self.is_closed = True
            self.accepted = False


class WebSocketManager:
    """Manages individual WebSocket connections."""

    def __init__(self, ttl_seconds: int = 3600):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.ttl_seconds = ttl_seconds
        self._cleanup_task: Optional[asyncio.Task] = None
        self._safe_mode = True  # Safe mode to prevent errors
        self._last_cleanup = time.time()

    async def start_cleanup_task(self) -> None:
        """Start the periodic cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._run_cleanup())
            logger.info("WebSocket manager cleanup task started")

    async def _run_cleanup(self) -> None:
        """Run cleanup periodically."""
        while True:
            try:
                await self.cleanup_expired_connections()
                self._last_cleanup = time.time()
            except Exception as e:
                logger.error(f"Error in WebSocket cleanup task: {str(e)}")

            # Run cleanup every minute, but use dynamic sleep to account for processing time
            elapsed = time.time() - self._last_cleanup
            sleep_time = max(5, 60 - elapsed)  # At least 5 seconds, at most 60
            await asyncio.sleep(sleep_time)

    async def cleanup_expired_connections(self) -> None:
        """Remove expired connections."""
        current_time = time.time()
        connections_cleaned = 0

        try:
            sessions_to_remove = []

            # Find expired sessions
            for session_id, connection in self.connections.items():
                if (
                    not connection.is_connected()
                    or current_time - connection.created_at > self.ttl_seconds
                ):
                    sessions_to_remove.append(session_id)
                    await connection.close()
                    connections_cleaned += 1

            # Remove expired sessions
            for session_id in sessions_to_remove:
                del self.connections[session_id]

            if connections_cleaned > 0:
                logger.debug(
                    f"WebSocket cleanup: removed {connections_cleaned} expired connections"
                )
        except Exception as e:
            logger.error(f"Error in cleanup_expired_connections: {e}")

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Register a new WebSocket connection for a session."""
        try:
            # Verify that the WebSocket has been properly accepted
            try:
                # For some implementations, checking the socket attribute can determine if accepted
                if hasattr(websocket, "socket") and not websocket.socket:
                    logger.warning(
                        "Attempted to register a WebSocket that wasn't properly accepted"
                    )
                    # We'll still register it, but mark its state accordingly
                    connection = WebSocketConnection(websocket)
                    connection.accepted = False
                else:
                    connection = WebSocketConnection(websocket)
            except Exception:
                # If we can't check, assume it's accepted (since at this point it should be)
                connection = WebSocketConnection(websocket)

            # Check if a connection already exists for this session and close it if it does
            if session_id in self.connections:
                old_connection = self.connections[session_id]
                if not old_connection.is_closed:
                    logger.warning(
                        f"Replacing existing connection for session {session_id}"
                    )
                    await old_connection.close()

            # Register the new connection
            self.connections[session_id] = connection
            logger.debug(f"Added WebSocket for session: {session_id}")
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {type(e).__name__}: {str(e)}")

    async def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a WebSocket connection for a session and mark associated jobs as disconnected."""
        try:
            if session_id not in self.connections:
                logger.debug(
                    f"No connection found for session {session_id} during disconnect"
                )
                return

            connection = self.connections[session_id]

            # Only close if this is the correct websocket
            if connection.websocket == websocket:
                await connection.close()
                del self.connections[session_id]
                logger.debug(f"Removed WebSocket for session: {session_id}")

                # Mark all running jobs for this session as disconnected
                await self.mark_jobs_disconnected(session_id)
            else:
                logger.debug(
                    f"WebSocket mismatch for session {session_id} during disconnect"
                )

        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {type(e).__name__}: {str(e)}")

    async def mark_jobs_disconnected(self, session_id: str) -> None:
        """Mark all jobs associated with a session as disconnected."""
        try:
            # Import here to avoid circular imports
            from app.services.processing.streaming_service import (
                mark_jobs_disconnected_for_session,
            )

            await mark_jobs_disconnected_for_session(session_id)
            logger.debug(f"Marked jobs disconnected for session: {session_id}")
        except Exception as e:
            logger.error(
                f"Error marking jobs as disconnected: {type(e).__name__}: {str(e)}"
            )

    async def send_message(self, message: dict, session_id: str) -> bool:
        """Send a message to a specific session's WebSocket connection.

        Args:
            message: The message to send
            session_id: The session ID to send the message to

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if session_id not in self.connections:
            logger.debug(f"No connection for session: {session_id}")
            return False

        connection = self.connections[session_id]

        # Skip if connection is already closed
        if connection.is_closed:
            logger.debug(f"Connection for session {session_id} is closed, removing")
            del self.connections[session_id]
            return False

        # Ensure message has required fields
        if "created_at" not in message:
            message["created_at"] = datetime.datetime.now().isoformat()

        # Handle planning_only flag - remove it before sending to client
        planning_only = message.pop("planning_only", False)

        # Preserve thought field for planning steps
        has_thought = "thought" in message and message["thought"]

        # Add status field if missing based on type
        if "status" not in message:
            if message.get("type") == "token":
                if planning_only:
                    message["status"] = "planning"
                else:
                    message["status"] = "processing"
            elif message.get("type") == "step":
                message["status"] = "planning"
            elif message.get("type") == "tool":
                message["status"] = "processing"
            elif message.get("type") == "error":
                message["status"] = "error"
            else:
                message["status"] = "complete"  # Default for other types

        # Handle step messages consistently
        if (
            message.get("type") == "step"
            and not has_thought
            and message.get("status") == "planning"
        ):
            message["thought"] = "Planning Phase"

        logger.debug(
            f"Sending message type: {message.get('type')}, status: {message.get('status')}"
        )

        # Try to send the message with a retry
        success = False
        try:
            success = await connection.send_message(message)
        except Exception as e:
            logger.debug(
                f"Error in first attempt to send message: {type(e).__name__}: {e}"
            )
            # If first attempt fails with "accept" error, mark as closed and return
            if "accept" in str(e).lower():
                connection.is_closed = True
                connection.accepted = False
                del self.connections[session_id]
                return False

            # Otherwise try one more time after a brief delay
            try:
                await asyncio.sleep(0.1)
                success = await connection.send_message(message)
            except Exception as e2:
                logger.debug(
                    f"Error in retry to send message: {type(e2).__name__}: {e2}"
                )
                connection.is_closed = True
                del self.connections[session_id]
                return False

        # If send failed, clean up the connection
        if not success:
            logger.debug(
                f"Failed to send message to session {session_id}, closing connection"
            )
            await connection.close()
            del self.connections[session_id]

        return success

    async def send_error(self, error_message: str, session_id: str) -> bool:
        """Send an error message to a specific session.

        Args:
            error_message: The error message to send
            session_id: The session ID to send the message to

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        try:
            if not error_message or not session_id:
                return False

            if session_id not in self.connections:
                logger.debug(f"No connection for session {session_id} to send error")
                return False

            return await self.send_message(
                {
                    "type": "error",
                    "message": error_message,
                    "status": "error",
                    "created_at": datetime.datetime.now().isoformat(),
                },
                session_id,
            )
        except Exception as e:
            logger.error(f"Error sending error message: {type(e).__name__}: {str(e)}")
            return False


# Create a singleton instance
websocket_manager = WebSocketManager()
