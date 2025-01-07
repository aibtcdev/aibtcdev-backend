from backend.factory import backend
from backend.models import ExtensionFilter, TaskCreate
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from storage3._async.bucket import Response
from typing import Any, Dict, Optional, Type, Union
from uuid import UUID


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
    profile_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000000"))
    agent_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000000"))

    def __init__(
        self,
        profile_id: UUID = UUID("00000000-0000-0000-0000-000000000000"),
        agent_id: UUID = UUID("00000000-0000-0000-0000-000000000000"),
        **kwargs,
    ):
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


class GetDAOListSchema(BaseModel):
    """Input schema for DAOList tool."""


class GetDAOListTool(BaseTool):
    name: str = "db_list_daos_daos"
    description: str = (
        "This tool is used to get/list all the daos and DAOS with their extensions and tokens. "
        "It returns a dictionary with three keys: 'daos', 'extensions', and 'tokens'. "
        "'daos' contains the list of daos and their details, "
        "'extensions' contains the list of extensions and their details, "
        "and 'tokens' contains the list of tokens and their details."
        "Example usage: "
        "can you show me what daos are avaliable? "
    )
    args_schema: Type[BaseModel] = GetDAOListSchema
    return_direct: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _deploy(
        self,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to list dao tasks."""
        try:
            daos = backend.list_daos()
            extensions = backend.list_extensions()
            tokens = backend.list_tokens()
            response = {
                "daos": daos,
                "extensions": extensions,
                "tokens": tokens,
            }

            return response
        except Exception as e:
            return {"error": str(e)}

    async def _run(
        self,
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync version of the tool."""
        return self._deploy(**kwargs)

    async def _arun(
        self,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(**kwargs)
