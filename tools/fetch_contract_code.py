# import requests
# from crewai_tools import BaseTool

# class FetchContractCodeTool(BaseTool):
#     """Tool for fetching contract code directly using user input."""
#     def __init__(self):
#         super().__init__(
#             name="FetchContractCodeTool", 
#             description="Fetches the contract code from the given user input",
#             args={"user_input": {"type": "string"}}  
#         )
    
#     def _run(self, user_input):
#         # Split the user_input into contract_address and contract_name
#         try:
#             contract_address, contract_name = user_input.split(".")
#         except ValueError:
#             return "Invalid input format. Use the format 'contract_address.contract_name'."
        
#         source_url = f"https://api.hiro.so/v2/contracts/source/{contract_address}/{contract_name}"
        
#         # Fetch data from the source endpoint
#         response = requests.get(source_url)
#         if response.status_code == 200:
#             source_data = response.json()
#             return f"Source Data: {source_data}"
#         else:
#             return f"Failed to fetch source data: {response.status_code}"


