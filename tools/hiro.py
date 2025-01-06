from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Type


class STXPriceInput(BaseModel):
    """Input for STXPriceTool."""

    pass


class STXPriceTool(BaseTool):
    """Tool for getting the current STX price."""

    name: str = "stacks_stx_price"
    description: str = "A tool that can be used to get the current STX price"
    args_schema: Type[BaseModel] = STXPriceInput
    return_direct: bool = False

    def _deploy(self, *args, **kwargs) -> float:
        """Get the current STX price.

        Returns:
            float: The current STX price
        """
        from lib.hiro import HiroApi

        api = HiroApi()
        return str(api.get_stx_price())

    def _run(self, *args, **kwargs) -> str:
        """Get the current STX price."""
        return self._deploy(*args, **kwargs)

    async def _arun(self, *args, **kwargs) -> str:
        """Async implementation of getting STX price."""
        return self._deploy(*args, **kwargs)
