from crewai_tools import BaseTool
from db.factory import db


class GetDaosTool(BaseTool):
    name: str = "Database: Get Daos"
    description: str = "Retrieve daos from the database"

    def _run(self) -> dict:
        """
        Retrieve daos from the database.

        Args:

        Returns:
            dict: Daos data.
        """
        return db.get_daos()
