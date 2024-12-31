from crewai_tools import BaseTool
from lib.hiro import HiroApi
from pydantic import BaseModel, Field
from typing import Type


class STXPriceTool(BaseTool):
    name: str = "STX: Get Current Price"
    description: str = "Retrieve the current price of STX."

    def _run(self) -> str:
        """
        Retrieve the current price of STX.

        Returns:
            str: The current price of STX.
        """
        obj = HiroApi()
        return str(obj.get_stx_price())
