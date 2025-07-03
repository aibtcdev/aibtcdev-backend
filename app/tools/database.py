from typing import Any, Dict, Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.backend.factory import backend
from app.backend.models import (
    UUID,
    ExtensionFilter,
    TaskBase,
    TaskCreate,
    TaskFilter,
    TokenFilter,
)


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
        if self.profile_id is None:
            return {"error": "Profile ID is required"}
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
        "This tool is used to get/list all the daos and DAOS with their single token and DEX extension. "
        "It returns a structured response containing DAOs, each with its associated token and DEX extension. "
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
            # Get all DAOs
            daos = backend.list_daos()
            dao_data = []

            for dao in daos:
                # Get the single token for this DAO
                tokens = backend.list_tokens(filters=TokenFilter(dao_id=dao.id))
                token = tokens[0] if tokens else None

                # Combine data for this DAO (without DEX extension)
                dao_info = {"dao": dao, "token": token}
                dao_data.append(dao_info)

            return {"dao_data": dao_data}
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
    """Input schema for SearchDAO tool."""

    name: Optional[str] = Field(
        None,
        description="Name or partial name of the DAO to search for",
    )
    description: Optional[str] = Field(
        None,
        description="Description text to search for in DAO descriptions",
    )
    token_name: Optional[str] = Field(
        None,
        description="Name or partial name of the token associated with the DAO",
    )
    token_symbol: Optional[str] = Field(
        None,
        description="Symbol or partial symbol of the token associated with the DAO",
    )
    contract_id: Optional[str] = Field(
        None,
        description="Contract ID or partial contract ID to search for",
    )


class GetDAOByNameTool(BaseTool):
    name: str = "dao_search"
    description: str = (
        "This tool is used to search for DAOs using multiple criteria including name, description, token name, "
        "token symbol, and contract ID. All search parameters are optional, but at least one must be provided. "
        "The search supports partial matches and is case-insensitive. "
        "It returns comprehensive DAO details including contract principals for the DAO and its associated token. "
        "The returned data includes DAO name, description, contract addresses/principals, token information (symbol, "
        "name, contract principal), and DEX extension details if available. "
        "Example usage: 'find daos related to bitcoin', 'search for daos with ETH in their token symbol', "
        "or 'find daos that mention governance in their description'"
    )
    args_schema: Type[BaseModel] = GetDAOByNameInput
    return_direct: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _deploy(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        token_name: Optional[str] = None,
        token_symbol: Optional[str] = None,
        contract_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to search for DAOs by multiple criteria."""
        try:
            # Ensure at least one search parameter is provided
            if not any([name, description, token_name, token_symbol, contract_id]):
                return {"error": "At least one search parameter must be provided"}

            daos = backend.list_daos()
            matching_daos = []

            for dao in daos:
                # Get tokens and extensions for this DAO
                tokens = backend.list_tokens(filters=TokenFilter(dao_id=dao.id))
                extensions = backend.list_extensions(
                    filters=ExtensionFilter(dao_id=dao.id)
                )

                # Check matches based on name
                name_match = name and name.lower() in dao.name.lower()

                # Check matches based on description
                desc_match = (
                    description and description.lower() in dao.description.lower()
                )

                # Check matches based on contract ID
                contract_match = contract_id and any(
                    contract_id.lower() in str(dao.contract_id).lower()
                )

                # Check matches based on token name or symbol
                token_name_match = False
                token_symbol_match = False

                if tokens:
                    token_name_match = token_name and any(
                        token_name.lower() in token.name.lower() for token in tokens
                    )
                    token_symbol_match = token_symbol and any(
                        token_symbol.lower() in token.symbol.lower() for token in tokens
                    )

                # Add to matching results if any criteria match
                if any(
                    [
                        name_match,
                        desc_match,
                        contract_match,
                        token_name_match,
                        token_symbol_match,
                    ]
                ):
                    matching_daos.append(
                        {"dao": dao, "extensions": extensions, "tokens": tokens}
                    )

            if matching_daos:
                return {"matches": matching_daos}
            else:
                search_terms = []
                if name:
                    search_terms.append(f"name: '{name}'")
                if description:
                    search_terms.append(f"description: '{description}'")
                if token_name:
                    search_terms.append(f"token name: '{token_name}'")
                if token_symbol:
                    search_terms.append(f"token symbol: '{token_symbol}'")
                if contract_id:
                    search_terms.append(f"contract ID: '{contract_id}'")

                return {"error": f"No DAOs found matching {', '.join(search_terms)}"}
        except Exception as e:
            return {"error": str(e)}

    async def _run(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        token_name: Optional[str] = None,
        token_symbol: Optional[str] = None,
        contract_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync version of the tool."""
        return self._deploy(
            name=name,
            description=description,
            token_name=token_name,
            token_symbol=token_symbol,
            contract_id=contract_id,
            **kwargs,
        )

    async def _arun(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        token_name: Optional[str] = None,
        token_symbol: Optional[str] = None,
        contract_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            name=name,
            description=description,
            token_name=token_name,
            token_symbol=token_symbol,
            contract_id=contract_id,
            **kwargs,
        )


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
        description="Whether the schedule is enabled or not (true or false) default is true",
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
            if self.profile_id is None:
                return {"error": "Profile ID is required"}
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
            if self.profile_id is None:
                return {"error": "Profile ID is required"}
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
        if self.profile_id is None:
            return {"error": "Profile ID is required"}
        if not self.agent_id:
            return {"error": "Agent ID is required"}
        try:
            return backend.delete_task(UUID(task_id))
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
