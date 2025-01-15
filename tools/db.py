from backend.factory import backend
from backend.models import (
    UUID,
    ExtensionFilter,
    TaskBase,
    TaskCreate,
    TaskFilter,
    TokenFilter,
)
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Type


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


class AddScheduledTaskTool(BaseTool):
    name: str = "db_add_scheduled_task"
    description: str = (
        "Add a scheduled task to the database with specified name, prompt, cron schedule, and enabled status"
        "Example usage: 'add a task named 'bitcoin price' to run every hour' or 'enable the task named 'bitcoin price'"
    )
    args_schema: Type[BaseModel] = AddScheduledTaskInput
    return_direct: bool = False
    profile_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None

    def __init__(
        self,
        profile_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
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
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to add a scheduled task."""

        if not self.agent_id:
            return {"error": "Agent ID is required"}
        try:
            response = backend.create_task(
                TaskCreate(
                    prompt=prompt,
                    agent_id=self.agent_id,
                    profile_id=self.profile_id,
                    name=name,
                    is_scheduled=True,
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
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync version of the tool."""
        return self._deploy(name, prompt, cron, **kwargs)

    async def _arun(
        self,
        name: str,
        prompt: str,
        cron: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(name, prompt, cron, **kwargs)


class GetDAOListSchema(BaseModel):
    """Input schema for DAOList tool."""


class GetDAOListTool(BaseTool):
    name: str = "dao_list"
    description: str = (
        "This tool is used to get/list all the daos and DAOS with their extensions and tokens. "
        "It returns a dictionary with three keys: 'daos', 'extensions', and 'tokens'. "
        "'daos' contains the list of daos and their details, "
        "'extensions' contains the list of extensions and their details, "
        "and 'tokens' contains the list of tokens and their details."
        "Example usage: 'show me all the daos' or 'list all the daos' or 'get all the daos'"
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
            return backend.list_daos()
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


class GetDAOByNameInput(BaseModel):
    """Input schema for GetDAOByName tool."""

    name: str = Field(
        ...,
        description="Name or partial name of the DAO to search for",
    )


class GetDAOByNameTool(BaseTool):
    name: str = "dao_get_by_name"
    description: str = (
        "This tool is used to search for DAOs by name, supporting partial matches. "
        "It returns details for all DAOs that have similar names to the search term. "
        "Example usage: 'find daos related to bitcoin' or 'search for eth daos'"
    )
    args_schema: Type[BaseModel] = GetDAOByNameInput
    return_direct: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _deploy(
        self,
        name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to search for DAOs by name."""
        try:
            daos = backend.list_daos()
            # Search for DAOs with names containing the search term (case-insensitive)
            matching_daos = [dao for dao in daos if name.lower() in dao.name.lower()]

            if matching_daos:
                results = []
                for dao in matching_daos:
                    extensions = backend.list_extensions(
                        filters=ExtensionFilter(dao_id=dao.id)
                    )
                    tokens = backend.list_tokens(filters=TokenFilter(dao_id=dao.id))
                    results.append(
                        {"dao": dao, "extensions": extensions, "tokens": tokens}
                    )
                return {"matches": results}
            else:
                return {"error": f"No DAOs found matching '{name}'"}
        except Exception as e:
            return {"error": str(e)}

    async def _run(
        self,
        name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync version of the tool."""
        return self._deploy(name=name, **kwargs)

    async def _arun(
        self,
        name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(name=name, **kwargs)


class UpdateScheduledTaskInput(BaseModel):
    """Input schema for UpdateScheduledTask tool."""

    task_id: str = Field(
        ...,
        description="ID of the scheduled task to update",
    )
    name: Optional[str] = Field(
        None,
        description="New name for the scheduled task",
    )
    prompt: Optional[str] = Field(
        None,
        description="New prompt for the task",
    )
    cron: Optional[str] = Field(
        None,
        description="New cron expression for the schedule, e.g. '0 0 * * *' for every day at midnight",
    )
    enabled: Optional[str] = Field(
        None,
        description="Whether the schedule is enabled or not (true or false)",
    )


class UpdateScheduledTaskTool(BaseTool):
    name: str = "db_update_scheduled_task"
    description: str = (
        "Update an existing scheduled task in the database. You can update the name, prompt, cron schedule, "
        "and enabled status. Only the fields that are provided will be updated."
        "Example usage: 'update the task named 'bitcoin price' to run every hour' or 'enable the task named 'bitcoin price'"
        "Example usage 2: 'disable the task named 'bitcoin price'"
    )
    args_schema: Type[BaseModel] = UpdateScheduledTaskInput
    return_direct: bool = False
    profile_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None

    def __init__(
        self,
        profile_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.profile_id = profile_id
        self.agent_id = agent_id

    def _deploy(
        self,
        task_id: str,
        name: Optional[str] = None,
        prompt: Optional[str] = None,
        cron: Optional[str] = None,
        enabled: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to update a scheduled task."""
        try:
            if not self.agent_id:
                return {"error": "Agent ID is required"}
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if prompt is not None:
                update_data["prompt"] = prompt
            if cron is not None:
                update_data["cron"] = cron
            if enabled is not None:
                update_data["is_scheduled"] = bool(enabled)

            response = backend.update_task(
                UUID(task_id),
                TaskBase(
                    **update_data,
                    agent_id=self.agent_id,
                    profile_id=self.profile_id,
                ),
            )
            return response
        except Exception as e:
            return {"error": str(e)}

    async def _run(
        self,
        task_id: str,
        name: Optional[str] = None,
        prompt: Optional[str] = None,
        cron: Optional[str] = None,
        enabled: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync version of the tool."""
        return self._deploy(task_id, name, prompt, cron, enabled, **kwargs)

    async def _arun(
        self,
        task_id: str,
        name: Optional[str] = None,
        prompt: Optional[str] = None,
        cron: Optional[str] = None,
        enabled: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(task_id, name, prompt, cron, enabled, **kwargs)


class ListScheduledTasksSchema(BaseModel):
    """Input schema for ListScheduledTasks tool."""


class ListScheduledTasksTool(BaseTool):
    name: str = "db_list_scheduled_tasks"
    description: str = (
        "List all scheduled tasks for the current agent. Returns a list of tasks with their details "
        "including ID, name, prompt, cron schedule, and enabled status."
    )
    args_schema: Type[BaseModel] = ListScheduledTasksSchema
    return_direct: bool = False
    profile_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None

    def __init__(
        self,
        profile_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.profile_id = profile_id
        self.agent_id = agent_id

    def _deploy(
        self,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to list scheduled tasks."""
        try:
            if not self.agent_id:
                return {"error": "Agent ID is required"}
            tasks = backend.list_tasks(
                filters=TaskFilter(agent_id=self.agent_id, profile_id=self.profile_id)
            )
            # Filter to only return scheduled tasks
            scheduled_tasks = [task for task in tasks if task.is_scheduled]
            return {"tasks": scheduled_tasks}
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


class DeleteScheduledTaskInput(BaseModel):
    """Input schema for DeleteScheduledTask tool."""

    task_id: str = Field(
        ...,
        description="ID of the scheduled task to delete",
    )


class DeleteScheduledTaskTool(BaseTool):
    name: str = "db_delete_scheduled_task"
    description: str = "Delete a scheduled task from the database using its ID."
    args_schema: Type[BaseModel] = DeleteScheduledTaskInput
    return_direct: bool = False
    profile_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None

    def __init__(
        self,
        profile_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.profile_id = profile_id
        self.agent_id = agent_id

    def _deploy(
        self,
        task_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to delete a scheduled task."""
        try:
            if not self.agent_id:
                return {"error": "Agent ID is required"}
            response = backend.delete_task(UUID(task_id))
            return response
        except Exception as e:
            return {"error": str(e)}

    async def _run(
        self,
        task_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync version of the tool."""
        return self._deploy(task_id, **kwargs)

    async def _arun(
        self,
        task_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(task_id, **kwargs)
