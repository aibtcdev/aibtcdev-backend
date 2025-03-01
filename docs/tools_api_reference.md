# Tools API Reference

This document provides a technical reference for the Tools API, which allows you to discover and interact with the available tools in the system.

## API Endpoint

```
GET /tools/available
```

## Authentication

Authentication is required for all API requests. Provide one of the following:

- **Bearer Token**: Include in the `Authorization` header as `Bearer <token>`
- **API Key**: Include in the `X-API-Key` header

## Response Format

The API returns a JSON array of tool objects, each with the following structure:

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "category": "string",
  "parameters": "string"
}
```

### Tool Object Fields

| Field         | Type   | Description                                                |
|---------------|--------|------------------------------------------------------------|
| `id`          | string | Unique identifier for the tool (e.g., "faktory_exec_buy")  |
| `name`        | string | Display name of the tool (e.g., "Exec Buy")                |
| `description` | string | Human-readable description of the tool's functionality      |
| `category`    | string | Category the tool belongs to (e.g., "FAKTORY", "WALLET")   |
| `parameters`  | string | JSON string containing parameter information (see below)   |

### Parameters Format

The `parameters` field is a JSON string that, when parsed, contains an object mapping parameter names to their details:

```json
{
  "parameter_name": {
    "description": "string",
    "type": "string"
  }
}
```

| Field         | Type   | Description                                           |
|---------------|--------|-------------------------------------------------------|
| `description` | string | Human-readable description of the parameter           |
| `type`        | string | Data type of the parameter (e.g., "str", "int")       |

## Example Request

```bash
curl -X GET "https://api.example.com/tools/available" \
  -H "Authorization: Bearer your_token_here"
```

## Example Response

```json
[
  {
    "id": "wallet_get_my_balance",
    "name": "Get My Balance",
    "description": "Retrieve the current balance of your wallet",
    "category": "WALLET",
    "parameters": "{\"wallet_id\":{\"description\":\"ID of the wallet\",\"type\":\"UUID\"}}"
  },
  {
    "id": "faktory_get_token",
    "name": "Get Token",
    "description": "Get information about a token on Faktory",
    "category": "FAKTORY",
    "parameters": "{\"token_id\":{\"description\":\"ID of the token\",\"type\":\"str\"},\"wallet_id\":{\"description\":\"ID of the wallet\",\"type\":\"UUID\"}}"
  }
]
```

## Error Responses

| Status Code | Description                | Response Body                                      |
|-------------|----------------------------|---------------------------------------------------|
| 401         | Unauthorized               | `{"detail": "Not authenticated"}`                  |
| 403         | Forbidden                  | `{"detail": "Not authorized to access this API"}`  |
| 500         | Internal Server Error      | `{"detail": "Failed to serve available tools: [error message]"}` |

## Tool Categories

Tools are organized into the following categories:

| Category     | Description                                           |
|--------------|-------------------------------------------------------|
| WALLET       | Tools for wallet management and transactions          |
| DAO          | Tools for DAO operations and governance               |
| FAKTORY      | Tools for interacting with the Faktory marketplace    |
| JING         | Tools for the Jing.js trading platform                |
| CONTRACTS    | Tools for smart contract interactions                 |
| DATABASE     | Tools for database operations                         |
| STACKS       | Tools for Stacks blockchain interactions              |
| ALEX         | Tools for ALEX DEX operations                         |
| BITFLOW      | Tools for Bitflow trading platform                    |
| VELAR        | Tools for Velar protocol interactions                 |
| LUNARCRUSH   | Tools for LunarCrush data and analytics               |
| STXCITY      | Tools for STX City platform                           |

## Available Tools

The system provides a wide range of tools across different categories. Here are some examples:

### Wallet Tools
- `wallet_get_my_balance`: Get your wallet balance
- `wallet_get_my_address`: Get your wallet address
- `wallet_send_stx`: Send STX to another address
- `wallet_send_sip10`: Send SIP-10 tokens to another address

### DAO Tools
- `dao_charter_get_current`: Get the current DAO charter
- `dao_messaging_send`: Send a message through the DAO
- `dao_payments_get_invoice`: Get invoice details
- `dao_treasury_get_allowed_asset`: Check if an asset is allowed in the treasury

### Market Tools
- `faktory_exec_buy`: Execute a buy order on Faktory
- `faktory_get_token`: Get token information from Faktory
- `jing_get_order_book`: Get the order book from Jing.js
- `jing_submit_bid`: Submit a bid on Jing.js

## Implementation Notes

- The Tools API is designed to be used by both human users and AI agents
- Tool availability may depend on user permissions and wallet configuration
- Some tools require specific parameters like `wallet_id` which are automatically populated when possible
- Tool responses are standardized but vary based on the specific tool functionality

## Rate Limiting

The Tools API implements rate limiting to prevent abuse:

- Maximum of 60 requests per minute per user
- Maximum of 1000 requests per day per user

When rate limits are exceeded, the server will return a 429 Too Many Requests response.

## API Versioning

The current API version is v1. Future versions may be introduced with breaking changes.

To ensure compatibility, clients should:

1. Handle unknown fields in responses gracefully
2. Check for API announcements regarding deprecation and new features 