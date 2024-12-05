from typing import Dict, Set
from fastapi import WebSocket
from lib.logger import configure_logger

logger = configure_logger(__name__)

class ConnectionManager:
    def __init__(self):
        # Store both job and conversation connections
        self.job_connections: Dict[str, Set[WebSocket]] = {}
        self.conversation_connections: Dict[str, Set[WebSocket]] = {}

    async def connect_job(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.job_connections:
            self.job_connections[job_id] = set()
        self.job_connections[job_id].add(websocket)
        logger.debug(f"New WebSocket connection for job {job_id}")

    async def connect_conversation(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        if conversation_id not in self.conversation_connections:
            self.conversation_connections[conversation_id] = set()
        self.conversation_connections[conversation_id].add(websocket)
        logger.debug(f"New WebSocket connection for conversation {conversation_id}")

    async def disconnect_job(self, websocket: WebSocket, job_id: str):
        if job_id in self.job_connections:
            self.job_connections[job_id].discard(websocket)
            if not self.job_connections[job_id]:
                del self.job_connections[job_id]
        logger.debug(f"Closed WebSocket connection for job {job_id}")

    async def disconnect_conversation(self, websocket: WebSocket, conversation_id: str):
        if conversation_id in self.conversation_connections:
            self.conversation_connections[conversation_id].discard(websocket)
            if not self.conversation_connections[conversation_id]:
                del self.conversation_connections[conversation_id]
        logger.debug(f"Closed WebSocket connection for conversation {conversation_id}")

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

    async def send_conversation_message(self, message: dict, conversation_id: str):
        if conversation_id in self.conversation_connections:
            dead_connections = set()
            for connection in self.conversation_connections[conversation_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to conversation WebSocket: {str(e)}")
                    dead_connections.add(connection)
            
            # Clean up dead connections
            for dead in dead_connections:
                self.conversation_connections[conversation_id].discard(dead)
            if not self.conversation_connections[conversation_id]:
                del self.conversation_connections[conversation_id]

    async def broadcast_job_error(self, error_message: str, job_id: str):
        await self.send_job_message({
            "type": "error",
            "message": error_message
        }, job_id)

    async def broadcast_conversation_error(self, error_message: str, conversation_id: str):
        await self.send_conversation_message({
            "type": "error",
            "message": error_message
        }, conversation_id)

manager = ConnectionManager()
