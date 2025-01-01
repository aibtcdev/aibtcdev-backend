from backend.factory import backend
from backend.models import ScheduleCreate
from crewai_tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type


class AddScheduledTaskToolSchema(BaseModel):
    """Input schema for AddScheduledTaskTool."""

    name: str = Field(
        ...,
        description="Name of the scheduled task",
    )
    task: str = Field(
        ...,
        description="Task to add the schedule to",
    )
    cron: str = Field(
        ...,
        description="Cron expression for the schedule, e.g. '0 0 * * *' for every day at midnight",
    )
    enabled: str = Field(
        ...,
        description="Whether the schedule is enabled or not (true or false)",
    )


class AddScheduledTaskTool(BaseTool):
    name: str = "Database: Add Scheduled task"
    description: str = "Add a scheduled task to the database"
    args_schema: Type[BaseModel] = AddScheduledTaskToolSchema
    profile_id: str = "0"

    def __init__(self, profile_id: str, **kwargs):
        super().__init__(**kwargs)
        self.profile_id = profile_id

    def _run(self, name: str, task: str, cron: str, enabled: str) -> dict:
        """
        Add a scheduled task to the database.

        Args:
            name (str): Name of the scheduled task
            task (str): Task to add the schedule to
            cron (str): Cron expression for the schedule, e.g. '0 0 * * *' for every day at midnight
            enabled (str): Whether the schedule is enabled or not (true or false)

        Returns:
            dict: Response data.
        """
        try:
            response = backend.create_schedule(
                ScheduleCreate(
                    profile_id=self.profile_id,
                    name=name,
                    task=task,
                    cron=cron,
                    enabled=bool(enabled),
                )
            )
            return response
        except Exception as e:
            return {"error": str(e)}
