import asyncio
import time
from typing import Any, Dict, Optional, Set, Tuple
from uuid import UUID

from fastapi import WebSocket

from lib.logger import configure_logger

logger = configure_logger(__name__)


class WebSocketConnection:
    """Represents a single WebSocket connection with metadata."""

    def __init__(self, websocket: WebSocket, created_at: float = None):
        self.websocket = websocket
        self.created_at = created_at or time.time()
        self.is_closed = False
        self.metadata: Dict[str, Any] = {}

    async def send_message(self, message: dict) -> bool:
        """Safely send a message to this connection.

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if self.is_closed:
            return False

        try:
            await self.websocket.send_json(message)
            return True
        except Exception as e:
            logger.debug(f"Error sending message: {e}")
            self.is_closed = True
            return False

    async def close(self) -> None:
        """Safely close this WebSocket connection."""
        if not self.is_closed:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
            finally:
                self.is_closed = True


class WebSocketManager:
    """Manages WebSocket connections and message distribution."""

    def __init__(self, ttl_seconds: int = 3600):
        self.session_connections: Dict[str, Set[WebSocketConnection]] = {}
        self.ttl_seconds = ttl_seconds
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self) -> None:
        """Start the periodic cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._run_cleanup())

    async def _run_cleanup(self) -> None:
        """Run cleanup periodically."""
        while True:
            try:
                await self.cleanup_expired_connections()
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)  # Run cleanup every minute

    async def cleanup_expired_connections(self) -> None:
        """Remove expired connections."""
        current_time = time.time()

        sessions_to_remove = []
        for session_id, connections in self.session_connections.items():
            expired_connections = {
                conn
                for conn in connections
                if conn.is_closed or current_time - conn.created_at > self.ttl_seconds
            }

            # Close any expired connections that aren't already closed
            for conn in expired_connections:
                await conn.close()

            # Remove expired connections from the set
            self.session_connections[session_id] = {
                conn for conn in connections if conn not in expired_connections
            }

            # If no connections remain, mark for removal
            if not self.session_connections[session_id]:
                sessions_to_remove.append(session_id)

        # Remove empty sessions
        for session_id in sessions_to_remove:
            del self.session_connections[session_id]

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Register a new WebSocket connection for a session."""
        if session_id not in self.session_connections:
            self.session_connections[session_id] = set()

        connection = WebSocketConnection(websocket)
        self.session_connections[session_id].add(connection)
        logger.debug(f"Added WebSocket to session: {session_id}")

    async def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a WebSocket connection for a session and mark associated jobs as disconnected."""
        if session_id not in self.session_connections:
            return

        connections_to_remove = {
            conn
            for conn in self.session_connections[session_id]
            if conn.websocket == websocket
        }

        # Mark connections as closed and remove them
        for conn in connections_to_remove:
            conn.is_closed = True

        self.session_connections[session_id] = {
            conn
            for conn in self.session_connections[session_id]
            if conn.websocket != websocket
        }

        # If no connections remain, clean up the session
        if not self.session_connections[session_id]:
            del self.session_connections[session_id]

        # Mark all running jobs for this session as disconnected
        await self.mark_jobs_disconnected(session_id)

        logger.debug(f"Removed WebSocket from session: {session_id}")

    async def mark_jobs_disconnected(self, session_id: str) -> None:
        """Mark all jobs associated with a session as disconnected."""
        # Import here to avoid circular imports
        from services.chat import mark_jobs_disconnected_for_session

        mark_jobs_disconnected_for_session(session_id)

    async def broadcast(self, message: dict, session_id: str) -> None:
        """Send a message to all WebSocket connections for a session."""
        if session_id not in self.session_connections:
            logger.debug(f"No active connections for session: {session_id}")
            return

        active_connections = set()
        connections_to_remove = set()

        for conn in self.session_connections[session_id]:
            if await conn.send_message(message):
                active_connections.add(conn)
            else:
                connections_to_remove.add(conn)

        # Update the connections
        self.session_connections[session_id] = active_connections

        # If no connections remain, clean up the session
        if not self.session_connections[session_id]:
            del self.session_connections[session_id]

    async def broadcast_error(self, error_message: str, session_id: str) -> None:
        """Send an error message to all WebSocket connections for a session."""
        await self.broadcast({"type": "error", "message": error_message}, session_id)


# Create a singleton instance
websocket_manager = WebSocketManager()
