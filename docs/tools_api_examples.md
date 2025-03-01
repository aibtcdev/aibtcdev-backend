# Tools API Examples

This document provides practical examples of how to use the Tools API in various programming languages and scenarios.

## Basic Usage

The Tools API allows you to discover and interact with the available tools in the system. The primary endpoint is:

```
GET /tools/available
```

This endpoint returns a list of all available tools, their descriptions, and parameter requirements.

## Authentication

All requests to the Tools API require authentication. You can use either a Bearer token or an API key.

### Using a Bearer Token

```bash
curl -X GET "https://api.example.com/tools/available" \
  -H "Authorization: Bearer your_token_here"
```

### Using an API Key

```bash
curl -X GET "https://api.example.com/tools/available" \
  -H "X-API-Key: your_api_key_here"
```

## Example: Fetching Available Tools

### Python Example

```python
import requests

def get_available_tools(api_url, api_key=None, bearer_token=None):
    """Fetch available tools from the API.
    
    Args:
        api_url: Base URL of the API
        api_key: Optional API key for authentication
        bearer_token: Optional bearer token for authentication
        
    Returns:
        List of available tools
    """
    headers = {}
    
    if api_key:
        headers["X-API-Key"] = api_key
    elif bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    else:
        raise ValueError("Either api_key or bearer_token must be provided")
    
    response = requests.get(f"{api_url}/tools/available", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error fetching tools: {response.status_code} - {response.text}")

# Example usage
api_url = "https://api.example.com"
bearer_token = "your_token_here"

try:
    tools = get_available_tools(api_url, bearer_token=bearer_token)
    
    # Print all tool names and descriptions
    for tool in tools:
        print(f"{tool['name']}: {tool['description']}")
        
    # Find tools in a specific category
    wallet_tools = [tool for tool in tools if tool['category'] == "WALLET"]
    print(f"\nFound {len(wallet_tools)} wallet tools:")
    for tool in wallet_tools:
        print(f"- {tool['name']}")
        
except Exception as e:
    print(f"Error: {e}")
```

### JavaScript Example

```javascript
async function getAvailableTools(apiUrl, apiKey = null, bearerToken = null) {
  const headers = {};
  
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  } else if (bearerToken) {
    headers['Authorization'] = `Bearer ${bearerToken}`;
  } else {
    throw new Error('Either apiKey or bearerToken must be provided');
  }
  
  try {
    const response = await fetch(`${apiUrl}/tools/available`, { headers });
    
    if (!response.ok) {
      throw new Error(`Error fetching tools: ${response.status} - ${await response.text()}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch tools:', error);
    throw error;
  }
}

// Example usage
const apiUrl = 'https://api.example.com';
const bearerToken = 'your_token_here';

getAvailableTools(apiUrl, null, bearerToken)
  .then(tools => {
    // Print all tool names and descriptions
    tools.forEach(tool => {
      console.log(`${tool.name}: ${tool.description}`);
    });
    
    // Find tools in a specific category
    const daoTools = tools.filter(tool => tool.category === 'DAO');
    console.log(`\nFound ${daoTools.length} DAO tools:`);
    daoTools.forEach(tool => {
      console.log(`- ${tool.name}`);
    });
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

## Working with Tool Parameters

Each tool has a `parameters` field that contains a JSON string with information about the required parameters. Here's how to parse and use this information:

### Python Example

```python
import json

def parse_tool_parameters(tool):
    """Parse the parameters JSON string from a tool object.
    
    Args:
        tool: Tool object from the API
        
    Returns:
        Dictionary of parameter information
    """
    return json.loads(tool['parameters'])

# Example usage
tools = get_available_tools(api_url, bearer_token=bearer_token)

# Find a specific tool
wallet_send_tool = next((tool for tool in tools if tool['id'] == 'wallet_send_stx'), None)

if wallet_send_tool:
    # Parse parameters
    parameters = parse_tool_parameters(wallet_send_tool)
    
    print(f"Parameters for {wallet_send_tool['name']}:")
    for param_name, param_info in parameters.items():
        print(f"- {param_name}: {param_info['description']} (Type: {param_info['type']})")
```

### JavaScript Example

```javascript
function parseToolParameters(tool) {
  return JSON.parse(tool.parameters);
}

// Example usage
getAvailableTools(apiUrl, null, bearerToken)
  .then(tools => {
    // Find a specific tool
    const faktoryBuyTool = tools.find(tool => tool.id === 'faktory_exec_buy');
    
    if (faktoryBuyTool) {
      // Parse parameters
      const parameters = parseToolParameters(faktoryBuyTool);
      
      console.log(`Parameters for ${faktoryBuyTool.name}:`);
      Object.entries(parameters).forEach(([paramName, paramInfo]) => {
        console.log(`- ${paramName}: ${paramInfo.description} (Type: ${paramInfo.type})`);
      });
    }
  });
```

## Filtering Tools by Category

You can filter tools by category to find the ones relevant to your use case:

### Python Example

```python
def get_tools_by_category(tools, category):
    """Filter tools by category.
    
    Args:
        tools: List of tools from the API
        category: Category to filter by
        
    Returns:
        List of tools in the specified category
    """
    return [tool for tool in tools if tool['category'] == category]

# Example usage
tools = get_available_tools(api_url, bearer_token=bearer_token)

# Get all categories
categories = set(tool['category'] for tool in tools)
print(f"Available categories: {', '.join(categories)}")

# Get tools for each category
for category in categories:
    category_tools = get_tools_by_category(tools, category)
    print(f"\n{category} Tools ({len(category_tools)}):")
    for tool in category_tools:
        print(f"- {tool['name']}")
```

## Searching for Tools

You can search for tools by name or description:

### Python Example

```python
def search_tools(tools, query):
    """Search for tools by name or description.
    
    Args:
        tools: List of tools from the API
        query: Search query string
        
    Returns:
        List of tools matching the query
    """
    query = query.lower()
    return [
        tool for tool in tools 
        if query in tool['name'].lower() or query in tool['description'].lower()
    ]

# Example usage
tools = get_available_tools(api_url, bearer_token=bearer_token)

# Search for tools related to "balance"
balance_tools = search_tools(tools, "balance")
print(f"Found {len(balance_tools)} tools related to 'balance':")
for tool in balance_tools:
    print(f"- {tool['name']}: {tool['description']}")
```

## Complete Application Example

Here's a more complete example that demonstrates how to build a simple tool explorer application:

### Python Example (Flask)

```python
from flask import Flask, render_template, request, jsonify
import requests
import json

app = Flask(__name__)

API_URL = "https://api.example.com"
API_KEY = "your_api_key_here"  # In production, store this securely

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tools')
def get_tools():
    try:
        headers = {"X-API-Key": API_KEY}
        response = requests.get(f"{API_URL}/tools/available", headers=headers)
        
        if response.status_code != 200:
            return jsonify({"error": f"API error: {response.status_code}"}), 500
            
        tools = response.json()
        
        # Process tools if needed
        for tool in tools:
            # Parse parameters for easier use in frontend
            tool['parsed_parameters'] = json.loads(tool['parameters'])
            
        return jsonify(tools)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tools/search')
def search_tools():
    query = request.args.get('q', '').lower()
    category = request.args.get('category', '')
    
    try:
        # Get all tools first
        headers = {"X-API-Key": API_KEY}
        response = requests.get(f"{API_URL}/tools/available", headers=headers)
        
        if response.status_code != 200:
            return jsonify({"error": f"API error: {response.status_code}"}), 500
            
        tools = response.json()
        
        # Filter by category if specified
        if category:
            tools = [tool for tool in tools if tool['category'] == category]
            
        # Filter by search query if specified
        if query:
            tools = [
                tool for tool in tools 
                if query in tool['name'].lower() or query in tool['description'].lower()
            ]
            
        return jsonify(tools)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
```

With corresponding HTML template:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Tools Explorer</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .tool-card { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; }
        .tool-header { display: flex; justify-content: space-between; }
        .tool-category { background: #f0f0f0; padding: 5px 10px; border-radius: 3px; }
        .search-container { margin-bottom: 20px; }
        .filters { display: flex; gap: 10px; margin-bottom: 15px; }
        select, input { padding: 8px; }
        .parameters { margin-top: 10px; }
        .parameter { margin-bottom: 5px; }
    </style>
</head>
<body>
    <h1>Tools Explorer</h1>
    
    <div class="search-container">
        <div class="filters">
            <input type="text" id="search" placeholder="Search tools..." />
            <select id="category-filter">
                <option value="">All Categories</option>
            </select>
        </div>
        <button id="search-button">Search</button>
    </div>
    
    <div id="tools-container"></div>
    
    <script>
        // Fetch all tools on page load
        fetch('/api/tools')
            .then(response => response.json())
            .then(tools => {
                displayTools(tools);
                populateCategoryFilter(tools);
            })
            .catch(error => console.error('Error fetching tools:', error));
            
        // Search functionality
        document.getElementById('search-button').addEventListener('click', () => {
            const query = document.getElementById('search').value;
            const category = document.getElementById('category-filter').value;
            
            fetch(`/api/tools/search?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`)
                .then(response => response.json())
                .then(tools => {
                    displayTools(tools);
                })
                .catch(error => console.error('Error searching tools:', error));
        });
        
        function displayTools(tools) {
            const container = document.getElementById('tools-container');
            container.innerHTML = '';
            
            if (tools.length === 0) {
                container.innerHTML = '<p>No tools found matching your criteria.</p>';
                return;
            }
            
            tools.forEach(tool => {
                const toolCard = document.createElement('div');
                toolCard.className = 'tool-card';
                
                const header = document.createElement('div');
                header.className = 'tool-header';
                
                const title = document.createElement('h2');
                title.textContent = tool.name;
                
                const category = document.createElement('span');
                category.className = 'tool-category';
                category.textContent = tool.category;
                
                header.appendChild(title);
                header.appendChild(category);
                
                const description = document.createElement('p');
                description.textContent = tool.description;
                
                const parametersTitle = document.createElement('h3');
                parametersTitle.textContent = 'Parameters';
                
                const parameters = document.createElement('div');
                parameters.className = 'parameters';
                
                const parsedParams = JSON.parse(tool.parameters);
                Object.entries(parsedParams).forEach(([paramName, paramInfo]) => {
                    const param = document.createElement('div');
                    param.className = 'parameter';
                    param.innerHTML = `<strong>${paramName}</strong>: ${paramInfo.description} <em>(${paramInfo.type})</em>`;
                    parameters.appendChild(param);
                });
                
                toolCard.appendChild(header);
                toolCard.appendChild(description);
                toolCard.appendChild(parametersTitle);
                toolCard.appendChild(parameters);
                
                container.appendChild(toolCard);
            });
        }
        
        function populateCategoryFilter(tools) {
            const categories = [...new Set(tools.map(tool => tool.category))];
            const select = document.getElementById('category-filter');
            
            categories.forEach(category => {
                const option = document.createElement('option');
                option.value = category;
                option.textContent = category;
                select.appendChild(option);
            });
        }
    </script>
</body>
</html>
```

## Conclusion

The Tools API provides a flexible way to discover and interact with the various tools available in the system. By using the examples in this document, you can build applications that leverage these tools for wallet management, DAO operations, market interactions, and more.

Remember to always authenticate your requests and handle errors appropriately to ensure a smooth user experience. 