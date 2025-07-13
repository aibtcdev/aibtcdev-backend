# API Overview

This document provides a comprehensive overview of all available API endpoints in aibtcdev-backend.

## Table of Contents

- [Authentication](#authentication)
- [Tools API](#tools-api)
- [Usage Examples](#usage-examples)
- [Webhooks API](#webhooks-api)
- [Response Formats](#response-formats)
- [Error Handling](#error-handling)

## Authentication

All API endpoints require authentication using one of the following methods:

- **Bearer Token**: `Authorization: Bearer <token>`
- **API Key**: `X-API-Key: <api_key>`

## Tools API

Base path: `/tools`

### Tool Discovery

#### Get Available Tools
- **Endpoint**: `GET /tools/`
- **Query Parameters**:
  - `category` (optional): Filter tools by category
- **Description**: Returns a list of all available tools with their descriptions

#### Get Tool Categories
- **Endpoint**: `GET /tools/categories`
- **Description**: Returns a list of all available tool categories

#### Search Tools
- **Endpoint**: `GET /tools/search`
- **Query Parameters**:
  - `query` (required): Search query for tool name or description
  - `category` (optional): Filter by category
- **Description**: Search for tools by name or description

### Trading & Finance

#### Execute Faktory Buy Order
- **Endpoint**: `POST /tools/faktory/execute_buy`
- **Body Parameters**:
  - `btc_amount` (string): Amount of BTC to spend
  - `dao_token_dex_contract_address` (string): Contract principal where the DAO token is listed
  - `slippage` (string, optional): Slippage tolerance in basis points (default: "15")
- **Description**: Execute a buy order on Faktory DEX

#### Fund Wallet with Testnet STX
- **Endpoint**: `POST /tools/wallet/fund_testnet_faucet`
- **Description**: Request testnet STX tokens from the faucet

#### Fund with Testnet sBTC
- **Endpoint**: `POST /tools/wallet/fund_testnet_sbtc`
- **Description**: Request testnet sBTC tokens from Faktory faucet

### DAO Management

#### Create DAO Action Proposal
- **Endpoint**: `POST /tools/dao/action_proposals/propose_send_message`
- **Body Parameters**:
  - `agent_account_contract` (string): Contract principal of the agent account
  - `action_proposals_voting_extension` (string): Contract principal for DAO action proposals
  - `action_proposal_contract_to_execute` (string): Contract principal of the action proposal
  - `dao_token_contract_address` (string): Contract principal of the DAO token
  - `message` (string): Message to be sent through the DAO proposal system
  - `memo` (string, optional): Optional memo for the proposal
- **Description**: Create a proposal for sending a message via the DAO action proposal system

#### Veto DAO Action Proposal
- **Endpoint**: `POST /tools/dao/action_proposals/veto_proposal`
- **Body Parameters**:
  - `dao_action_proposal_voting_contract` (string): Contract principal for DAO action proposals
  - `proposal_id` (string): ID of the proposal to veto
- **Description**: Veto an existing DAO action proposal

#### Generate Proposal Recommendation
- **Endpoint**: `POST /tools/dao/proposal_recommendations/generate`
- **Body Parameters**:
  - `dao_id` (UUID): The ID of the DAO
  - `focus_area` (string, optional): Specific area of focus (default: "general improvement")
  - `specific_needs` (string, optional): Specific needs or requirements
  - `model_name` (string, optional): LLM model to use (default: "x-ai/grok-4")
  - `temperature` (number, optional): Temperature for LLM generation (default: 0.1)
- **Description**: Generate AI-powered proposal recommendations for a DAO

### Agent Account Management

#### Approve Contract for Agent Account
- **Endpoint**: `POST /tools/agent_account/approve_contract`
- **Body Parameters**:
  - `agent_account_contract` (string): Contract principal of the agent account
  - `contract_to_approve` (string): The contract principal to approve
- **Description**: Approve a contract for use with an agent account

### AI Evaluation

#### Run Comprehensive Evaluation
- **Endpoint**: `POST /tools/evaluation/comprehensive`
- **Body Parameters**:
  - `proposal_id` (string): Unique identifier for the proposal
  - `proposal_content` (string, optional): Override proposal content
  - `dao_id` (UUID, optional): DAO ID for context
  - `custom_system_prompt` (string, optional): Custom system prompt
  - `custom_user_prompt` (string, optional): Custom user prompt
  - `config` (object, optional): Configuration for the evaluation agent
- **Description**: Run comprehensive AI evaluation on a proposal

#### Get Default Evaluation Prompts
- **Endpoint**: `GET /tools/evaluation/default_prompts`
- **Description**: Get the default system and user prompts for comprehensive evaluation

### Social Media Integration

#### Get Twitter Embed Data
- **Endpoint**: `GET /tools/social/twitter_embed`
- **Query Parameters**:
  - `url` (required): Twitter/X.com URL to embed
  - `media_max_width` (optional): Maximum width for media (default: 560)
  - `hide_thread` (optional): Whether to hide the thread (default: false)
- **Description**: Proxy endpoint for Twitter oembed API to avoid CORS issues

## Usage Examples

This section provides practical examples of how to use the various API endpoints.

### Tool Discovery

#### Get Available Tools
```bash
curl -H "Authorization: Bearer your_token" \
  http://localhost:8000/tools/
```

#### Search for Specific Tools
```bash
curl -H "Authorization: Bearer your_token" \
  "http://localhost:8000/tools/search?query=faktory&category=trading"
```

### Trading & Finance

#### Execute Faktory Buy Order
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{"btc_amount": "0.0004", "dao_token_dex_contract_address": "SP..."}' \
  http://localhost:8000/tools/faktory/execute_buy
```

#### Fund Wallet with Testnet STX
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://localhost:8000/tools/wallet/fund_testnet_faucet
```

#### Fund with Testnet sBTC
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://localhost:8000/tools/wallet/fund_testnet_sbtc
```

### DAO Management

#### Create DAO Action Proposal
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_account_contract": "SP...",
    "action_proposals_voting_extension": "SP...",
    "action_proposal_contract_to_execute": "SP...",
    "dao_token_contract_address": "SP...",
    "message": "Proposal to improve DAO governance",
    "memo": "Optional memo for the proposal"
  }' \
  http://localhost:8000/tools/dao/action_proposals/propose_send_message
```

#### Veto DAO Action Proposal
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "dao_action_proposal_voting_contract": "SP...",
    "proposal_id": "123"
  }' \
  http://localhost:8000/tools/dao/action_proposals/veto_proposal
```

#### Generate Proposal Recommendation
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "dao_id": "12345678-1234-1234-1234-123456789abc",
    "focus_area": "community growth",
    "specific_needs": "Need to increase member engagement"
  }' \
  http://localhost:8000/tools/dao/proposal_recommendations/generate
```

### Agent Account Management

#### Approve Contract for Agent Account
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_account_contract": "SP...",
    "contract_to_approve": "SP..."
  }' \
  http://localhost:8000/tools/agent_account/approve_contract
```

### AI Evaluation

#### Run Comprehensive Evaluation
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "proposal_id": "prop-123",
    "dao_id": "12345678-1234-1234-1234-123456789abc"
  }' \
  http://localhost:8000/tools/evaluation/comprehensive
```

#### Get Default Evaluation Prompts
```bash
curl -H "Authorization: Bearer your_token" \
  http://localhost:8000/tools/evaluation/default_prompts
```

### Social Media Integration

#### Get Twitter Embed Data
```bash
curl -H "Authorization: Bearer your_token" \
  "http://localhost:8000/tools/social/twitter_embed?url=https://x.com/username/status/123"
```

#### Get Twitter Embed with Custom Settings
```bash
curl -H "Authorization: Bearer your_token" \
  "http://localhost:8000/tools/social/twitter_embed?url=https://x.com/username/status/123&media_max_width=400&hide_thread=true"
```

### JavaScript/TypeScript Examples

#### Using fetch() for API calls
```javascript
// Get available tools
const response = await fetch('http://localhost:8000/tools/', {
  headers: {
    'Authorization': 'Bearer your_token'
  }
});
const tools = await response.json();

// Execute Faktory buy order
const buyResponse = await fetch('http://localhost:8000/tools/faktory/execute_buy', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your_token',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    btc_amount: '0.0004',
    dao_token_dex_contract_address: 'SP...'
  })
});
const buyResult = await buyResponse.json();
```

#### Using axios for API calls
```javascript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Authorization': 'Bearer your_token'
  }
});

// Create DAO proposal
const proposalResponse = await apiClient.post('/tools/dao/action_proposals/propose_send_message', {
  agent_account_contract: 'SP...',
  action_proposals_voting_extension: 'SP...',
  action_proposal_contract_to_execute: 'SP...',
  dao_token_contract_address: 'SP...',
  message: 'Proposal to improve DAO governance'
});
```

### Python Examples

#### Using requests library
```python
import requests

headers = {
    'Authorization': 'Bearer your_token'
}

# Get available tools
response = requests.get('http://localhost:8000/tools/', headers=headers)
tools = response.json()

# Execute Faktory buy order
buy_data = {
    'btc_amount': '0.0004',
    'dao_token_dex_contract_address': 'SP...'
}
buy_response = requests.post(
    'http://localhost:8000/tools/faktory/execute_buy',
    headers={**headers, 'Content-Type': 'application/json'},
    json=buy_data
)
buy_result = buy_response.json()
```

#### Using httpx (async)
```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        # Get available tools
        response = await client.get(
            'http://localhost:8000/tools/',
            headers={'Authorization': 'Bearer your_token'}
        )
        tools = response.json()
        
        # Create DAO proposal
        proposal_data = {
            'agent_account_contract': 'SP...',
            'action_proposals_voting_extension': 'SP...',
            'action_proposal_contract_to_execute': 'SP...',
            'dao_token_contract_address': 'SP...',
            'message': 'Proposal to improve DAO governance'
        }
        proposal_response = await client.post(
            'http://localhost:8000/tools/dao/action_proposals/propose_send_message',
            headers={'Authorization': 'Bearer your_token'},
            json=proposal_data
        )
        proposal_result = proposal_response.json()

asyncio.run(main())
```

## Webhooks API

Base path: `/webhooks`

### Blockchain Event Processing

#### Chainhook Webhook
- **Endpoint**: `POST /webhooks/chainhook`
- **Authentication**: Bearer token via `Authorization` header
- **Description**: Process blockchain events from chainhook services
- **Returns**: 204 No Content (processes asynchronously)

#### DAO Creation Webhook
- **Endpoint**: `POST /webhooks/dao`
- **Authentication**: Bearer token via `Authorization` header
- **Description**: Handle DAO creation events and setup associated entities
- **Returns**: JSON response with created entity details

## Response Formats

### Success Response (Tools API)
```json
{
  "success": true,
  "output": "Operation completed successfully",
  "data": { ... }
}
```

### Error Response
```json
{
  "type": "error",
  "message": "Description of the error"
}
```

### Webhook Response
```json
{
  "status": "success",
  "message": "Webhook processed successfully",
  "data": { ... }
}
```

## Error Handling

### HTTP Status Codes
- `200`: Success
- `204`: No Content (for async webhook processing)
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (invalid or missing authentication)
- `404`: Not Found (resource doesn't exist)
- `408`: Request Timeout
- `500`: Internal Server Error

### Common Error Types
- **Authentication Errors**: Invalid or expired tokens
- **Validation Errors**: Missing or invalid request parameters
- **Resource Errors**: Requested resource not found
- **Network Errors**: Blockchain or external service connectivity issues
- **Rate Limit Errors**: API rate limits exceeded

### Error Response Format
All errors follow a consistent format:
```json
{
  "detail": "Error description"
}
```

For webhook authentication errors:
```json
{
  "detail": "Invalid authentication token"
}
```
