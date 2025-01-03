from backend.factory import backend
from backend.models import TaskCreate
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from storage3._async.bucket import Response
from typing import Any, Dict, Optional, Type, Union


class AddScheduledTaskInput(BaseModel):
    """Input schema for AddScheduledTask tool."""

    name: str = Field(
        ...,
        description="Name of the scheduled task",
    )
    prompt: str = Field(
        ...,
        description="Prompt to schedule",
    )
    cron: str = Field(
        ...,
        description="Cron expression for the schedule, e.g. '0 0 * * *' for every day at midnight",
    )
    enabled: str = Field(
        ...,
        description="Whether the schedule is enabled or not (true or false) (default: true)",
    )


class AddScheduledTaskTool(BaseTool):
    name: str = "db_add_scheduled_task"
    description: str = (
        "Add a scheduled task to the database with specified name, prompt, cron schedule, and enabled status"
    )
    args_schema: Type[BaseModel] = AddScheduledTaskInput
    return_direct: bool = False
    profile_id: str = "0"
    agent_id: str = "0"

    def __init__(self, profile_id: str = "0", agent_id: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.profile_id = profile_id
        self.agent_id = agent_id

    def _deploy(
        self,
        name: str,
        prompt: str,
        cron: str,
        enabled: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to add a scheduled task."""
        try:
            response = backend.create_task(
                TaskCreate(
                    prompt=prompt,
                    agent_id=self.agent_id,
                    profile_id=self.profile_id,
                    name=name,
                    is_enabled=bool(enabled),
                    cron=cron,
                )
            )
            return response
        except Exception as e:
            return {"error": str(e)}

    async def _run(
        self,
        name: str,
        prompt: str,
        cron: str,
        enabled: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync version of the tool."""
        return self._deploy(name, prompt, cron, enabled, **kwargs)

    async def _arun(
        self,
        name: str,
        prompt: str,
        cron: str,
        enabled: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(name, prompt, cron, enabled, **kwargs)
