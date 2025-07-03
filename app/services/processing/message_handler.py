import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Message:
    """Base message structure for chat communication."""

    content: str
    type: str
    thread_id: str
    tool: Optional[str] = None
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    agent_id: Optional[str] = None
    role: str = "assistant"
    status: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class MessageHandler:
    """Handler for token-type messages."""

    def process_token_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a token message and prepare it for streaming."""
        # Default to processing status if not specified
        status = message.get("status", "processing")

        return {
            "type": "token",
            "status": status,  # Use the status or default to "processing"
            "content": message.get("content", ""),
            "created_at": datetime.datetime.now().isoformat(),
            "role": "assistant",
            "thread_id": message.get("thread_id"),
            "agent_id": message.get("agent_id"),
        }


class StepMessageHandler:
    """Handler for step/planning messages."""

    def process_step_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a planning step message."""
        # Ensure we have a timestamp for proper ordering
        timestamp = datetime.datetime.now().isoformat()

        return {
            "type": "step",
            "status": "planning",  # Always use planning status for steps
            "content": message.get("content", ""),
            "thought": message.get("thought"),
            "created_at": message.get("created_at", timestamp),
            "role": "assistant",
            "thread_id": message.get("thread_id"),
            "agent_id": message.get("agent_id"),
            # Add a special flag to identify this as a planning-only message
            "planning_only": True,
        }


class ToolExecutionHandler:
    """Handler for tool execution messages."""

    def process_tool_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a tool execution message."""
        # Use provided status or default to "processing"
        status = message.get("status", "processing")

        return {
            "role": "assistant",
            "type": "tool",
            "status": status,  # Use the exact status passed from the tool execution
            "tool": message.get("tool"),
            "tool_input": message.get("input"),
            "tool_output": message.get("output"),
            "created_at": datetime.datetime.now().isoformat(),
            "thread_id": message.get("thread_id"),
            "agent_id": message.get("agent_id"),
        }
