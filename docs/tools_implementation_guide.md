# Tools Implementation Guide

This document provides a step-by-step guide on how to implement new tools in the system.

## Overview

Tools are modular components that provide specific functionality to the system. Each tool follows a standard interface, making it easy to add new capabilities without modifying the core codebase.

## Prerequisites

Before implementing a new tool, you should have:

1. A clear understanding of the functionality you want to implement
2. Familiarity with Python and the Pydantic library
3. Access to the codebase and development environment

## Tool Structure

Each tool consists of:

1. A Pydantic model defining the input parameters
2. A class that implements the tool functionality
3. Registration in the tools factory

## Step 1: Define the Tool Category

Tools are organized by category. Choose an existing category or create a new one if your tool doesn't fit into any existing categories:

- WALLET: Tools for wallet management and transactions
- DAO: Tools for DAO operations and governance
- FAKTORY: Tools for interacting with the Faktory marketplace
- JING: Tools for the Jing.js trading platform
- CONTRACTS: Tools for smart contract interactions
- DATABASE: Tools for database operations
- STACKS: Tools for Stacks blockchain interactions
- ALEX: Tools for ALEX DEX operations
- BITFLOW: Tools for Bitflow trading platform
- VELAR: Tools for Velar protocol interactions
- LUNARCRUSH: Tools for LunarCrush data and analytics
- STXCITY: Tools for STX City platform

## Step 2: Create a New Tool File

Create a new Python file in the appropriate directory under the `tools/` folder. If you're creating a tool for a new category, you may need to create a new directory.

For example, if you're creating a new tool for the WALLET category, you might create a file at `tools/wallet/my_new_tool.py`.

## Step 3: Define the Tool Parameters

Define a Pydantic model for your tool's input parameters. This model will be used to validate the inputs and generate documentation.

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class MyNewToolParameters(BaseModel):
    """Parameters for MyNewTool."""
    
    param1: str = Field(
        ..., 
        description="Description of parameter 1"
    )
    param2: int = Field(
        default=0, 
        description="Description of parameter 2"
    )
    param3: Optional[List[str]] = Field(
        default=None, 
        description="Description of parameter 3"
    )
```

## Step 4: Implement the Tool Class

Create a class that implements your tool's functionality. The class should inherit from `BaseTool` and implement the required methods.

```python
from langchain.tools.base import BaseTool
from lib.logger import configure_logger
from typing import Any, Dict, Optional, Type

logger = configure_logger(__name__)

class MyNewTool(BaseTool):
    """Tool that provides [description of your tool's functionality]."""
    
    name = "category_my_new_tool"
    description = "Detailed description of what this tool does"
    args_schema: Type[BaseModel] = MyNewToolParameters
    
    def __init__(self, wallet_id: Optional[UUID] = None):
        """Initialize the tool.
        
        Args:
            wallet_id: Optional wallet ID to use for this tool
        """
        super().__init__()
        self.wallet_id = wallet_id
    
    def _run(self, param1: str, param2: int = 0, param3: Optional[List[str]] = None) -> Dict[str, Any]:
        """Execute the tool functionality.
        
        Args:
            param1: Description of parameter 1
            param2: Description of parameter 2
            param3: Description of parameter 3
            
        Returns:
            Dict containing the tool's output
            
        Raises:
            Exception: If an error occurs during execution
        """
        try:
            logger.info(f"Running {self.name} with params: {param1}, {param2}, {param3}")
            
            # Implement your tool's functionality here
            result = {}
            
            # Example implementation
            result["status"] = "success"
            result["data"] = {
                "param1": param1,
                "param2": param2,
                "param3": param3,
            }
            
            return result
        except Exception as e:
            logger.error(f"Error running {self.name}", exc_info=e)
            raise
    
    async def _arun(self, param1: str, param2: int = 0, param3: Optional[List[str]] = None) -> Dict[str, Any]:
        """Execute the tool functionality asynchronously.
        
        This method can be implemented if your tool supports async execution.
        If not needed, it can simply call the synchronous _run method.
        
        Args:
            param1: Description of parameter 1
            param2: Description of parameter 2
            param3: Description of parameter 3
            
        Returns:
            Dict containing the tool's output
        """
        return self._run(param1, param2, param3)
```

## Step 5: Register the Tool in the Factory

Import and register your tool in the `tools/tools_factory.py` file:

1. Import your tool at the top of the file:

```python
from .category.my_new_tool import MyNewTool
```

2. Add your tool to the `initialize_tools` function:

```python
def initialize_tools(
    profile: Optional[Profile] = None,
    agent_id: Optional[UUID] = None,
) -> Dict[str, LangChainBaseTool]:
    # ... existing code ...
    
    tools = {
        # ... existing tools ...
        "category_my_new_tool": MyNewTool(wallet_id),
    }
    
    return tools
```

## Step 6: Write Unit Tests

Create unit tests for your tool to ensure it works as expected. Tests should be placed in the `tests/tools/` directory.

```python
import pytest
from unittest.mock import MagicMock, patch
from tools.category.my_new_tool import MyNewTool

def test_my_new_tool_initialization():
    """Test that the tool initializes correctly."""
    tool = MyNewTool(wallet_id="test-wallet-id")
    assert tool.name == "category_my_new_tool"
    assert tool.wallet_id == "test-wallet-id"

def test_my_new_tool_run():
    """Test that the tool runs correctly."""
    tool = MyNewTool()
    
    # Mock any external dependencies
    with patch("some.external.dependency", MagicMock(return_value="mocked_result")):
        result = tool._run(param1="test", param2=42, param3=["a", "b", "c"])
    
    assert result["status"] == "success"
    assert result["data"]["param1"] == "test"
    assert result["data"]["param2"] == 42
    assert result["data"]["param3"] == ["a", "b", "c"]

def test_my_new_tool_error_handling():
    """Test that the tool handles errors correctly."""
    tool = MyNewTool()
    
    # Mock an external dependency to raise an exception
    with patch("some.external.dependency", MagicMock(side_effect=Exception("Test error"))):
        with pytest.raises(Exception) as excinfo:
            tool._run(param1="test")
    
    assert "Test error" in str(excinfo.value)
```

## Step 7: Document Your Tool

Add documentation for your tool in the appropriate documentation files:

1. Update the tool categories in `docs/tools_api_reference.md` if you've created a new category
2. Add examples of how to use your tool in `docs/tools_api_examples.md`

## Best Practices

### Naming Conventions

- Tool class names should be descriptive and follow PascalCase (e.g., `WalletGetBalanceTool`)
- Tool IDs should follow the format `category_action_noun` (e.g., `wallet_get_balance`)
- Parameter names should be descriptive and follow snake_case

### Error Handling

- Always use try/except blocks to catch and log errors
- Provide meaningful error messages
- Use the logger to log errors with appropriate context

### Documentation

- Provide detailed docstrings for your tool class and methods
- Include parameter descriptions in the Pydantic model
- Document any external dependencies or requirements

### Performance

- Consider the performance implications of your tool
- Implement caching where appropriate
- Use async methods for I/O-bound operations

## Example: Complete Tool Implementation

Here's a complete example of a tool that retrieves the price of a cryptocurrency:

```python
# tools/crypto/get_price.py
from langchain.tools.base import BaseTool
from lib.logger import configure_logger
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Type
import aiohttp
import uuid

logger = configure_logger(__name__)

class GetCryptoPriceParameters(BaseModel):
    """Parameters for the GetCryptoPrice tool."""
    
    symbol: str = Field(
        ..., 
        description="The cryptocurrency symbol (e.g., BTC, ETH)"
    )
    currency: str = Field(
        default="USD", 
        description="The currency to get the price in (e.g., USD, EUR)"
    )

class GetCryptoPriceTool(BaseTool):
    """Tool that retrieves the current price of a cryptocurrency."""
    
    name = "crypto_get_price"
    description = "Get the current price of a cryptocurrency in a specified currency"
    args_schema: Type[BaseModel] = GetCryptoPriceParameters
    
    def __init__(self, wallet_id: Optional[uuid.UUID] = None):
        """Initialize the tool.
        
        Args:
            wallet_id: Optional wallet ID (not used for this tool)
        """
        super().__init__()
        self.wallet_id = wallet_id
    
    def _run(self, symbol: str, currency: str = "USD") -> Dict[str, Any]:
        """Execute the tool functionality synchronously.
        
        This method delegates to the async version for simplicity.
        
        Args:
            symbol: The cryptocurrency symbol (e.g., BTC, ETH)
            currency: The currency to get the price in (e.g., USD, EUR)
            
        Returns:
            Dict containing the price information
        """
        import asyncio
        return asyncio.run(self._arun(symbol, currency))
    
    async def _arun(self, symbol: str, currency: str = "USD") -> Dict[str, Any]:
        """Execute the tool functionality asynchronously.
        
        Args:
            symbol: The cryptocurrency symbol (e.g., BTC, ETH)
            currency: The currency to get the price in (e.g., USD, EUR)
            
        Returns:
            Dict containing the price information
            
        Raises:
            Exception: If an error occurs during execution
        """
        try:
            logger.info(f"Getting price for {symbol} in {currency}")
            
            # Normalize inputs
            symbol = symbol.upper()
            currency = currency.upper()
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                url = f"https://api.example.com/v1/cryptocurrency/price"
                params = {"symbol": symbol, "currency": currency}
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API error: {response.status} - {error_text}")
                        return {
                            "status": "error",
                            "message": f"Failed to get price: {response.status}",
                        }
                    
                    data = await response.json()
            
            # Process and return the result
            return {
                "status": "success",
                "data": {
                    "symbol": symbol,
                    "currency": currency,
                    "price": data["price"],
                    "last_updated": data["last_updated"],
                }
            }
        except Exception as e:
            logger.error(f"Error getting price for {symbol}", exc_info=e)
            return {
                "status": "error",
                "message": f"Failed to get price: {str(e)}",
            }
```

## Troubleshooting

### Common Issues

1. **Tool not appearing in available tools**
   - Check that the tool is properly registered in `tools_factory.py`
   - Verify that the tool name follows the correct format

2. **Parameter validation errors**
   - Check that the parameters in your `_run` and `_arun` methods match the Pydantic model
   - Ensure that required parameters are provided

3. **Import errors**
   - Check for circular imports
   - Verify that all dependencies are installed

### Debugging Tips

- Use the logger to add debug statements
- Test your tool in isolation before integrating it
- Use the `pdb` debugger to step through your code

## Conclusion

By following this guide, you should be able to implement new tools that seamlessly integrate with the existing system. Remember to follow the established patterns and best practices to ensure consistency and reliability. 