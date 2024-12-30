from crewai_tools import BaseTool
from db.factory import db
from pydantic import BaseModel, Field
from typing import Type


class AddScheduledTaskToolSchema(BaseModel):
    """Input schema for AddScheduledTaskTool."""

    task: str = Field(
        ...,
        description="Task to add the schedule to",
    )
    cron: str = Field(
        ...,
        description="Cron expression for the schedule, e.g. '0 0 * * *' for every day at midnight",
    )
    enabled: bool = Field(
        ...,
        description="Whether the schedule is enabled or not",
    )


class AddScheduledTaskTool(BaseTool):
    name: str = "Database: Add Scheduled task"
    description: str = "Add a scheduled task to the database"
    args_schema: Type[BaseModel] = AddScheduledTaskToolSchema
    profile_id: str = "0"

    def __init__(self, profile_id: str, **kwargs):
        super().__init__(**kwargs)
        self.profile_id = profile_id

    def _run(self, task: str, cron: str, enabled: bool) -> dict:
        """
        Add a scheduled task to the database.

        Args:
            task (str): Task to add the schedule to
            cron (str): Cron expression for the schedule, e.g. '0 0 * * *' for every day at midnight
            enabled (bool): Whether the schedule is enabled or not

        Returns:
            dict: Response data.
        """
        return db.add_schedule(self.profile_id, task, cron, enabled)
