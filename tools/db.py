from backend.factory import backend
from backend.models import TaskCreate
from crewai_tools import BaseTool
from pydantic import BaseModel, Field
from storage3._async.bucket import Response
from typing import Type


class AddScheduledTaskToolSchema(BaseModel):
    """Input schema for AddScheduledTaskTool."""

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
    name: str = "Database: Add Scheduled task"
    description: str = "Add a scheduled task to the database"
    args_schema: Type[BaseModel] = AddScheduledTaskToolSchema
    profile_id: str = "0"
    agent_id: str = "0"

    def __init__(self, profile_id: str, agent_id: str, **kwargs):
        super().__init__(**kwargs)
        self.profile_id = profile_id
        self.agent_id = agent_id

    def _run(self, name: str, prompt: str, cron: str, enabled: str) -> dict:
        """
        Add a scheduled task to the database.

        Args:
            name (str): Name of the scheduled task
            prompt (str): Prompt to schedule
            cron (str): Cron expression for the schedule, e.g. '0 0 * * *' for every day at midnight
            enabled (str): Whether the schedule is enabled or not (true or false)

        Returns:
            dict: Response data.
        """
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
