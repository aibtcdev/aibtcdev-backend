import asyncio
import time
from fastapi import WebSocket
from lib.logger import configure_logger
from typing import Dict, Set, Tuple

logger = configure_logger(__name__)


class ConnectionManager:
    def __init__(self, ttl_seconds: int = 3600):  # Default 1 hour TTL
        # Store connections with their timestamps (websocket, timestamp)
        self.job_connections: Dict[str, Set[Tuple[WebSocket, float]]] = {}
        self.thread_connections: Dict[str, Set[Tuple[WebSocket, float]]] = {}
        self.session_connections: Dict[str, Set[Tuple[WebSocket, float]]] = {}
        self.ttl_seconds = ttl_seconds

    async def connect_job(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.job_connections:
            self.job_connections[job_id] = set()
        self.job_connections[job_id].add((websocket, time.time()))

    async def connect_thread(self, websocket: WebSocket, thread_id: str):
        await websocket.accept()
        if thread_id not in self.thread_connections:
            self.thread_connections[thread_id] = set()
        self.thread_connections[thread_id].add((websocket, time.time()))

    async def connect_session(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.session_connections:
            self.session_connections[session_id] = set()
        self.session_connections[session_id].add((websocket, time.time()))

    async def disconnect_job(self, websocket: WebSocket, job_id: str):
        if job_id in self.job_connections:
            self.job_connections[job_id] = {
                (ws, ts) for ws, ts in self.job_connections[job_id] if ws != websocket
            }
            if not self.job_connections[job_id]:
                del self.job_connections[job_id]

    async def disconnect_thread(self, websocket: WebSocket, thread_id: str):
        if thread_id in self.thread_connections:
            self.thread_connections[thread_id] = {
                (ws, ts)
                for ws, ts in self.thread_connections[thread_id]
                if ws != websocket
            }
            if not self.thread_connections[thread_id]:
                del self.thread_connections[thread_id]

    async def disconnect_session(self, websocket: WebSocket, session_id: str):
        if session_id in self.session_connections:
            self.session_connections[session_id] = {
                (ws, ts)
                for ws, ts in self.session_connections[session_id]
                if ws != websocket
            }
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]

    async def send_job_message(self, message: dict, job_id: str):
        if job_id in self.job_connections:
            dead_connections = set()
            active_connections = set()
            for ws, ts in self.job_connections[job_id]:
                try:
                    await ws.send_json(message)
                    active_connections.add(
                        (ws, time.time())
                    )  # Update timestamp on successful send
                except Exception as e:
                    logger.error(f"Error sending message to job WebSocket: {str(e)}")
                    dead_connections.add(ws)

            # Update connections with new timestamps and remove dead ones
            if active_connections or dead_connections:
                self.job_connections[job_id] = {conn for conn in active_connections}
                if not self.job_connections[job_id]:
                    del self.job_connections[job_id]

    async def send_thread_message(self, message: dict, thread_id: str):
        if thread_id in self.thread_connections:
            dead_connections = set()
            active_connections = set()
            for ws, ts in self.thread_connections[thread_id]:
                try:
                    await ws.send_json(message)
                    active_connections.add(
                        (ws, time.time())
                    )  # Update timestamp on successful send
                except Exception as e:
                    logger.error(f"Error sending message to thread WebSocket: {str(e)}")
                    dead_connections.add(ws)

            # Update connections with new timestamps and remove dead ones
            if active_connections or dead_connections:
                self.thread_connections[thread_id] = {
                    conn for conn in active_connections
                }
                if not self.thread_connections[thread_id]:
                    del self.thread_connections[thread_id]

    async def send_session_message(self, message: dict, session_id: str):
        if session_id in self.session_connections:
            dead_connections = set()
            active_connections = set()
            for ws, ts in self.session_connections[session_id]:
                try:
                    await ws.send_json(message)
                    active_connections.add(
                        (ws, time.time())
                    )  # Update timestamp on successful send
                except Exception as e:
                    logger.error(
                        f"Error sending message to session WebSocket: {str(e)}"
                    )
                    dead_connections.add(ws)

            # Update connections with new timestamps and remove dead ones
            if active_connections or dead_connections:
                self.session_connections[session_id] = {
                    conn for conn in active_connections
                }
                if not self.session_connections[session_id]:
                    del self.session_connections[session_id]

    async def cleanup_expired_connections(self):
        current_time = time.time()

        # Helper function to cleanup connections
        async def cleanup_connection_type(
            connections: Dict[str, Set[Tuple[WebSocket, float]]]
        ) -> None:
            ids_to_remove = []
            for id_, connections_set in connections.items():
                expired = {
                    (ws, ts)
                    for ws, ts in connections_set
                    if current_time - ts > self.ttl_seconds
                }
                if expired:
                    for ws, _ in expired:
                        try:
                            await ws.close()
                        except Exception as e:
                            logger.error(f"Error closing expired WebSocket: {str(e)}")
                    connections[id_] = connections_set - expired
                    if not connections[id_]:
                        ids_to_remove.append(id_)

            for id_ in ids_to_remove:
                del connections[id_]

        # Cleanup all connection types
        await cleanup_connection_type(self.job_connections)
        await cleanup_connection_type(self.thread_connections)
        await cleanup_connection_type(self.session_connections)

    async def start_cleanup_task(self):
        while True:
            try:
                await self.cleanup_expired_connections()
            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
            await asyncio.sleep(60)  # Run cleanup every minute

    async def broadcast_job_error(self, error_message: str, job_id: str):
        await self.send_job_message({"type": "error", "message": error_message}, job_id)

    async def broadcast_thread_error(self, error_message: str, thread_id: str):
        await self.send_thread_message(
            {"type": "error", "message": error_message}, thread_id
        )

    async def broadcast_session_error(self, error_message: str, session_id: str):
        await self.send_session_message(
            {"type": "error", "message": error_message}, session_id
        )


manager = ConnectionManager()
