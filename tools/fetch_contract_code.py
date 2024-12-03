from typing import Type
import requests
from crewai_tools import BaseTool
from pydantic import BaseModel, Field


class FetchContractCodeSchema(BaseModel):
    """Input schema for FetchContractCodeTool."""
    user_input: str = Field(
        ...,
        description="Contract identifier in the format 'contract_address.contract_name'"
    )


class FetchContractCodeTool(BaseTool):
    """Tool for fetching contract code directly using user input."""
    name: str = "FetchContractCodeTool"
    description: str = "Fetches the contract code from the given user input"
    args_schema: Type[BaseModel] = FetchContractCodeSchema

    def _run(self, user_input: str) -> str:
        """
        Fetch contract code using the provided contract identifier.

        Args:
            user_input (str): Contract identifier in format 'contract_address.contract_name'

        Returns:
            str: The contract source code data or an error message if the fetch fails.
        """
        # Split the user_input into contract_address and contract_name
        try:
            contract_address, contract_name = user_input.split(".")
        except ValueError:
            return "Invalid input format. Use the format 'contract_address.contract_name'."

        source_url = f"https://api.hiro.so/v2/contracts/source/{contract_address}/{contract_name}"

        # Fetch data from the source endpoint
        response = requests.get(source_url)
        if response.status_code == 200:
            source_data = response.json()
            return f"Source Data: {source_data}"
        else:
            return f"Failed to fetch source data: {response.status_code}"
