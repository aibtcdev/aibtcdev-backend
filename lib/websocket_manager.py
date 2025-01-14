from fastapi import WebSocket
from lib.logger import configure_logger
from typing import Dict, Set

logger = configure_logger(__name__)


class ConnectionManager:
    def __init__(self):
        # Store both job and thread connections
        self.job_connections: Dict[str, Set[WebSocket]] = {}
        self.thread_connections: Dict[str, Set[WebSocket]] = {}
        self.session_connections: Dict[str, Set[WebSocket]] = {}

    async def connect_job(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.job_connections:
            self.job_connections[job_id] = set()
        self.job_connections[job_id].add(websocket)

    async def connect_thread(self, websocket: WebSocket, thread_id: str):
        await websocket.accept()
        if thread_id not in self.thread_connections:
            self.thread_connections[thread_id] = set()
        self.thread_connections[thread_id].add(websocket)

    async def connect_session(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.session_connections:
            self.session_connections[session_id] = set()
        self.session_connections[session_id].add(websocket)

    async def disconnect_job(self, websocket: WebSocket, job_id: str):
        if job_id in self.job_connections:
            self.job_connections[job_id].discard(websocket)
            if not self.job_connections[job_id]:
                del self.job_connections[job_id]

    async def disconnect_thread(self, websocket: WebSocket, thread_id: str):
        if thread_id in self.thread_connections:
            self.thread_connections[thread_id].discard(websocket)
            if not self.thread_connections[thread_id]:
                del self.thread_connections[thread_id]

    async def disconnect_session(self, websocket: WebSocket, session_id: str):
        if session_id in self.session_connections:
            self.session_connections[session_id].discard(websocket)
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]

    async def send_job_message(self, message: dict, job_id: str):
        if job_id in self.job_connections:
            dead_connections = set()
            for connection in self.job_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to job WebSocket: {str(e)}")
                    dead_connections.add(connection)

            # Clean up dead connections
            for dead in dead_connections:
                self.job_connections[job_id].discard(dead)
            if not self.job_connections[job_id]:
                del self.job_connections[job_id]

    async def send_thread_message(self, message: dict, thread_id: str):
        if thread_id in self.thread_connections:
            dead_connections = set()
            for connection in self.thread_connections[thread_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to thread WebSocket: {str(e)}")
                    dead_connections.add(connection)

            # Clean up dead connections
            for dead in dead_connections:
                self.thread_connections[thread_id].discard(dead)
            if not self.thread_connections[thread_id]:
                del self.thread_connections[thread_id]

    async def send_session_message(self, message: dict, session_id: str):
        if session_id in self.session_connections:
            dead_connections = set()
            for connection in self.session_connections[session_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to thread WebSocket: {str(e)}")
                    dead_connections.add(connection)

            # Clean up dead connections
            for dead in dead_connections:
                self.session_connections[session_id].discard(dead)
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]

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
